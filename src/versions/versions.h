#pragma once

#include "common/cli.h"
#include "common/corpus.h"
#include "common/index.h"

// Додаткова інформація від версії про власний запуск
struct BuildStats {
    double setupMs = 0;  // підготовчий етап, що не входить у час обчислення (V1)
    double mergeMs = 0;  // злиття локальних індексів, входить у час обчислення (V4)
};

// V0 — послідовна версія, еталон коректності та базове значення часу
IndexParts buildV0(const Corpus& corpus, const Options& opt, BuildStats& stats);

// V1 — багатопотокова без синхронізації (навмисно некоректна)
IndexParts buildV1(const Corpus& corpus, const Options& opt, BuildStats& stats);

// V2 — одна блокувальна змінна на весь індекс
IndexParts buildV2(const Corpus& corpus, const Options& opt, BuildStats& stats);

// V3 — секціоноване блокування: K шардів, шард = hash(слово) mod K
IndexParts buildV3(const Corpus& corpus, const Options& opt, BuildStats& stats);

// V4 — локальні індекси потоків і злиття (seq: P-1 кроків, tree: log2 P кроків)
IndexParts buildV4(const Corpus& corpus, const Options& opt, BuildStats& stats);
