#include <functional>
#include <mutex>
#include <vector>

#include "common/tokenizer.h"
#include "versions/parallel.h"
#include "versions/versions.h"

// V3: секціоноване блокування. Індекс поділено на K шардів, кожен має власну
// блокувальну змінну; слово w належить шарду hash(w) mod K.
// Окрема таблиця на кожен шард обов'язкова: одна спільна unordered_map під
// різними м'ютексами некоректна, бо вставка з рехешуванням змінює всю таблицю.
// Шарди мають неперетинні множини слів, тому повертаються як частини індексу
// без додаткового злиття.

namespace {

// alignas(64) — щоб м'ютекси сусідніх шардів не ділили рядок кешу (хибне розділення)
struct alignas(64) Shard {
    std::mutex m;
    Index idx;
};

}  // namespace

IndexParts buildV3(const Corpus& corpus, const Options& opt, BuildStats& stats) {
    (void)stats;
    const size_t k = static_cast<size_t>(opt.k);
    std::vector<Shard> shards(k);
    const std::hash<std::string> hasher;

    forEachDocumentParallel(corpus, opt.threads, [&](const Document& d, int) {
        forEachToken(d.text, [&](const std::string& w) {
            Shard& s = shards[hasher(w) % k];  // хеш обчислюється поза критичною секцією
            std::lock_guard<std::mutex> lock(s.m);
            addOccurrence(s.idx[w], d.id);
        });
    });

    IndexParts parts;
    parts.reserve(k);
    for (Shard& s : shards) parts.push_back(std::move(s.idx));
    return parts;
}
