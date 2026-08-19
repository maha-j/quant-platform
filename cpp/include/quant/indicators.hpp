// quant/indicators.hpp — API publique des indicateurs critiques.
//
// C++20, RAII, aucune allocation manuelle exposée : les entrées/sorties sont des
// std::span (vues non-propriétaires) et std::vector (propriété RAII). Cette
// interface est stable et consommée par src/, les bindings Python et la DLL MQL5.
#pragma once

#include <cstddef>
#include <span>
#include <vector>

namespace quant {

/// Exponential Moving Average.
/// @param values série d'entrée.
/// @param period fenêtre (> 0).
/// @return série EMA de même taille que @p values.
[[nodiscard]] std::vector<double> ema(std::span<const double> values,
                                      std::size_t period);

/// Relative Strength Index (méthode de Wilder).
[[nodiscard]] std::vector<double> rsi(std::span<const double> close,
                                      std::size_t period = 14);

/// Average True Range (méthode de Wilder).
/// @pre high, low et close ont la même taille.
[[nodiscard]] std::vector<double> atr(std::span<const double> high,
                                      std::span<const double> low,
                                      std::span<const double> close,
                                      std::size_t period = 14);

}  // namespace quant
