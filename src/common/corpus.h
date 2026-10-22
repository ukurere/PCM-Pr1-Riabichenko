#pragma once

#include <cstdint>
#include <string>
#include <vector>

struct Document {
    int id;              // номер документа (docN)
    std::string name;    // ім'я файлу
    std::string text;    // вміст файлу (UTF-8)
};

struct Corpus {
    std::vector<Document> docs;
    uint64_t totalBytes = 0;
};

// Зчитує всі файли каталогу в пам'ять.
// Файли сортуються за іменем, номери документів призначаються в цьому порядку,
// тому нумерація однакова в усіх запусках.
Corpus loadCorpus(const std::string& dir);
