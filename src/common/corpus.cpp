#include "common/corpus.h"

#include <dirent.h>
#include <sys/stat.h>

#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>

// std::filesystem не використовується: у MinGW g++ 8.1 заголовок <filesystem> не компілюється.
// Імена файлів корпусу мають бути ASCII.

static std::vector<std::string> listFiles(const std::string& dir) {
    DIR* d = opendir(dir.c_str());
    if (!d) throw std::runtime_error("cannot open directory " + dir);
    std::vector<std::string> names;
    while (dirent* e = readdir(d)) {
        std::string name = e->d_name;
        if (name == "." || name == "..") continue;
        struct stat st;
        if (stat((dir + "/" + name).c_str(), &st) == 0 && S_ISREG(st.st_mode)) names.push_back(name);
    }
    closedir(d);
    std::sort(names.begin(), names.end());
    return names;
}

Corpus loadCorpus(const std::string& dir) {
    std::vector<std::string> names = listFiles(dir);

    Corpus corpus;
    corpus.docs.reserve(names.size());
    for (size_t i = 0; i < names.size(); ++i) {
        std::string path = dir + "/" + names[i];
        std::ifstream in(path, std::ios::binary);
        if (!in) throw std::runtime_error("cannot open " + path);
        std::ostringstream ss;
        ss << in.rdbuf();
        Document d;
        d.id = static_cast<int>(i);
        d.name = names[i];
        d.text = ss.str();
        corpus.totalBytes += d.text.size();
        corpus.docs.push_back(std::move(d));
    }
    return corpus;
}
