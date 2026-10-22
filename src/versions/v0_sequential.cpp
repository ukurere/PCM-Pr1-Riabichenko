#include "common/tokenizer.h"
#include "versions/versions.h"

IndexParts buildV0(const Corpus& corpus, const Options& opt, BuildStats& stats) {
    (void)opt;
    (void)stats;
    Index idx;
    for (const Document& d : corpus.docs) {
        forEachToken(d.text, [&](const std::string& w) { addOccurrence(idx[w], d.id); });
    }
    return singlePart(std::move(idx));
}
