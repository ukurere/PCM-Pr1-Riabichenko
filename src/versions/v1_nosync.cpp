#include <algorithm>

#include "common/timer.h"
#include "common/tokenizer.h"
#include "versions/parallel.h"
#include "versions/versions.h"

// V1 навмисно некоректна: потоки змінюють спільний індекс без взаємного виключення.
//
// Щоб гонка проявлялася саме як втрата оновлень, а не як аварійне завершення
// (паралельна вставка в unordered_map і vector руйнує їхню структуру), структуру
// індексу будує попередній послідовний прохід із нульовими лічильниками.
// Він не входить у час обчислення (stats.setupMs). Далі потоки лише знаходять
// наявні записи й збільшують лічильники.
//
// Лічильник posting.count для документа змінює лише потік, що обробляє цей документ,
// тому гонка виникає на спільному лічильнику entry.total (див. рядок RACE нижче).

IndexParts buildV1(const Corpus& corpus, const Options& opt, BuildStats& stats) {
    Timer setup;
    Index idx;
    for (const Document& d : corpus.docs) {
        forEachToken(d.text, [&](const std::string& w) { addOccurrence(idx[w], d.id); });
    }
    for (auto& kv : idx) {
        kv.second.total = 0;
        for (Posting& p : kv.second.postings) p.count = 0;
    }
    stats.setupMs = setup.elapsedMs();

    forEachDocumentParallel(corpus, opt.threads, [&](const Document& d, int) {
        forEachToken(d.text, [&](const std::string& w) {
            Entry& e = idx.find(w)->second;
            e.total++;  // RACE: читання total — додавання 1 — запис total без взаємного виключення
            auto it = std::lower_bound(e.postings.begin(), e.postings.end(), d.id,
                                       [](const Posting& p, int32_t doc) { return p.doc < doc; });
            it->count++;
        });
    });
    return singlePart(std::move(idx));
}
