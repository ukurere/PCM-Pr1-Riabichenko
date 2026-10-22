#include <mutex>

#include "common/tokenizer.h"
#include "versions/parallel.h"
#include "versions/versions.h"

// V2: увесь індекс захищено однією блокувальною змінною, яка захоплюється
// на час кожної операції оновлення (одного входження слова).
// Токенізація виконується паралельно, поза критичною секцією.

IndexParts buildV2(const Corpus& corpus, const Options& opt, BuildStats& stats) {
    (void)stats;
    Index idx;
    std::mutex m;
    forEachDocumentParallel(corpus, opt.threads, [&](const Document& d, int) {
        forEachToken(d.text, [&](const std::string& w) {
            std::lock_guard<std::mutex> lock(m);
            addOccurrence(idx[w], d.id);
        });
    });
    return singlePart(std::move(idx));
}
