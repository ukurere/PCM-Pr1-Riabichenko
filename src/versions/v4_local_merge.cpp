#include <algorithm>
#include <iterator>
#include <thread>
#include <vector>

#include "common/timer.h"
#include "common/tokenizer.h"
#include "versions/parallel.h"
#include "versions/versions.h"

// V4: кожен потік будує власний локальний індекс без синхронізації,
// після чого локальні індекси зливаються в результуючий.
// Замість витрат на синхронізацію з'являються витрати на злиття та
// додаткова пам'ять (слово, що трапляється в кількох потоках, зберігається кілька разів).

namespace {

// Зливає два впорядковані за doc списки в to (з кінця, без тимчасового буфера)
void mergePostings(std::vector<Posting>& to, const std::vector<Posting>& from) {
    size_t i = to.size(), j = from.size();
    to.resize(i + j);
    size_t out = to.size();
    while (j > 0) {
        if (i > 0 && to[i - 1].doc > from[j - 1].doc) to[--out] = to[--i];
        else to[--out] = from[--j];
    }
}

// Переносить усі записи src у dst; src стає порожнім.
// Документи різних потоків не перетинаються, тож для спільного слова досить
// злити два впорядковані за doc списки й додати total.
// Злиття симетричне, тому менший індекс переноситься в більший; місце в dst
// резервується заздалегідь, щоб уникнути повторних рехешувань.
void mergeInto(Index& dst, Index& src) {
    if (dst.size() < src.size()) std::swap(dst, src);
    dst.reserve(dst.size() + src.size());
    for (auto it = src.begin(); it != src.end();) {
        auto node = src.extract(it++);
        auto res = dst.insert(std::move(node));
        if (res.inserted) continue;

        Entry& to = res.position->second;
        Entry& from = res.node.mapped();
        to.total += from.total;
        mergePostings(to.postings, from.postings);
    }
    src = Index{};
}

// Послідовне приєднання локальних індексів до результуючого: P - 1 кроків
Index mergeSequential(std::vector<Index>& locals) {
    for (size_t i = 1; i < locals.size(); ++i) mergeInto(locals[0], locals[i]);
    return std::move(locals[0]);
}

// Попарне злиття за схемою збалансованого дерева: ceil(log2 P) кроків.
// На кроці з відстанню step індекс i поглинає індекс i + step; злиття в межах
// одного кроку незалежні й виконуються паралельно.
Index mergeTree(std::vector<Index>& locals) {
    const size_t p = locals.size();
    for (size_t step = 1; step < p; step *= 2) {
        std::vector<std::thread> pool;
        for (size_t i = 0; i + step < p; i += 2 * step) {
            pool.emplace_back([&locals, i, step] { mergeInto(locals[i], locals[i + step]); });
        }
        for (std::thread& th : pool) th.join();
    }
    return std::move(locals[0]);
}

}  // namespace

IndexParts buildV4(const Corpus& corpus, const Options& opt, BuildStats& stats) {
    std::vector<Index> locals(opt.threads);
    forEachDocumentParallel(corpus, opt.threads, [&](const Document& d, int tid) {
        Index& local = locals[tid];
        forEachToken(d.text, [&](const std::string& w) { addOccurrence(local[w], d.id); });
    });

    Timer merge;
    Index result = opt.merge == "seq" ? mergeSequential(locals) : mergeTree(locals);
    stats.mergeMs = merge.elapsedMs();
    return singlePart(std::move(result));
}
