// quant/indicators.cpp — implémentations haute performance.
//
// Style moderne : RAII (std::vector), pas de pointeurs bruts, pas de new/delete.
// Un seul parcours O(n) par indicateur ; les buffers sont pré-dimensionnés pour
// éviter les réallocations (optimisation CPU/mémoire).
#include "quant/indicators.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace quant {

std::vector<double> ema(std::span<const double> values, std::size_t period) {
    if (period == 0) {
        throw std::invalid_argument("ema: period doit être > 0");
    }
    std::vector<double> out(values.size());
    if (values.empty()) {
        return out;
    }
    const double alpha = 2.0 / (static_cast<double>(period) + 1.0);
    out[0] = values[0];
    for (std::size_t i = 1; i < values.size(); ++i) {
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1];
    }
    return out;
}

std::vector<double> rsi(std::span<const double> close, std::size_t period) {
    if (period == 0) {
        throw std::invalid_argument("rsi: period doit être > 0");
    }
    std::vector<double> out(close.size(), 100.0);
    if (close.size() < 2) {
        return out;
    }
    const double alpha = 1.0 / static_cast<double>(period);
    double avg_gain = 0.0;
    double avg_loss = 0.0;
    for (std::size_t i = 1; i < close.size(); ++i) {
        const double delta = close[i] - close[i - 1];
        const double gain = delta > 0.0 ? delta : 0.0;
        const double loss = delta < 0.0 ? -delta : 0.0;
        avg_gain = alpha * gain + (1.0 - alpha) * avg_gain;
        avg_loss = alpha * loss + (1.0 - alpha) * avg_loss;
        if (avg_loss == 0.0) {
            out[i] = 100.0;
        } else {
            const double rs = avg_gain / avg_loss;
            out[i] = 100.0 - 100.0 / (1.0 + rs);
        }
    }
    return out;
}

std::vector<double> atr(std::span<const double> high, std::span<const double> low,
                        std::span<const double> close, std::size_t period) {
    if (period == 0) {
        throw std::invalid_argument("atr: period doit être > 0");
    }
    if (high.size() != low.size() || low.size() != close.size()) {
        throw std::invalid_argument("atr: high/low/close de tailles différentes");
    }
    std::vector<double> out(close.size());
    if (close.empty()) {
        return out;
    }
    const double alpha = 1.0 / static_cast<double>(period);
    out[0] = high[0] - low[0];
    for (std::size_t i = 1; i < close.size(); ++i) {
        const double tr = std::max({high[i] - low[i],
                                    std::fabs(high[i] - close[i - 1]),
                                    std::fabs(low[i] - close[i - 1])});
        out[i] = alpha * tr + (1.0 - alpha) * out[i - 1];
    }
    return out;
}

}  // namespace quant
