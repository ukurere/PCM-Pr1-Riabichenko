#include "common/cli.h"

#include <cstdlib>
#include <iostream>

static void usage(const char* prog) {
    std::cerr << "Usage: " << prog
              << " --mode v0|v1|v2|v3|v4 --threads P [--k K] [--merge seq|tree]"
                 " --input DIR --output FILE\n";
    std::exit(2);
}

Options parseArgs(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (i + 1 >= argc) usage(argv[0]);
        std::string v = argv[++i];
        if (a == "--mode") o.mode = v;
        else if (a == "--threads") o.threads = std::atoi(v.c_str());
        else if (a == "--k") o.k = std::atoi(v.c_str());
        else if (a == "--merge") o.merge = v;
        else if (a == "--input") o.input = v;
        else if (a == "--output") o.output = v;
        else usage(argv[0]);
    }
    if (o.input.empty() || o.output.empty() || o.threads < 1 || o.k < 1) usage(argv[0]);
    if (o.merge != "seq" && o.merge != "tree") usage(argv[0]);
    return o;
}
