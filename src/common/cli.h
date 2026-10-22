#pragma once

#include <string>

struct Options {
    std::string mode = "v0";      // v0 | v1 | v2 | v3 | v4
    int threads = 1;              // P
    int k = 256;                  // кількість блокувальних змінних (V3)
    std::string merge = "tree";   // seq | tree (V4)
    std::string input;            // каталог корпусу
    std::string output;           // вихідний файл
};

// Розбирає аргументи; у разі помилки друкує довідку і завершує програму
Options parseArgs(int argc, char** argv);
