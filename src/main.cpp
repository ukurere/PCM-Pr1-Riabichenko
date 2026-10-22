#include <iostream>

#include "common/cli.h"
#include "common/corpus.h"
#include "common/output.h"
#include "common/timer.h"
#include "versions/versions.h"

int main(int argc, char** argv) {
    Options opt = parseArgs(argc, argv);

    Timer t;
    Corpus corpus = loadCorpus(opt.input);
    double readMs = t.elapsedMs();

    t.reset();
    IndexParts idx;
    BuildStats stats;
    if (opt.mode == "v0") idx = buildV0(corpus, opt, stats);
    else if (opt.mode == "v1") idx = buildV1(corpus, opt, stats);
    else if (opt.mode == "v2") idx = buildV2(corpus, opt, stats);
    else if (opt.mode == "v3") idx = buildV3(corpus, opt, stats);
    else if (opt.mode == "v4") idx = buildV4(corpus, opt, stats);
    else {
        std::cerr << "unknown mode: " << opt.mode << "\n";
        return 2;
    }
    double computeMs = t.elapsedMs() - stats.setupMs;

    t.reset();
    writeIndex(idx, opt.output);
    double writeMs = t.elapsedMs();

    std::cout << "read_ms=" << readMs
              << " setup_ms=" << stats.setupMs
              << " compute_ms=" << computeMs
              << " merge_ms=" << stats.mergeMs
              << " write_ms=" << writeMs
              << " docs=" << corpus.docs.size()
              << " bytes=" << corpus.totalBytes
              << " total_occurrences=" << totalOccurrences(idx) << "\n";
    return 0;
}
