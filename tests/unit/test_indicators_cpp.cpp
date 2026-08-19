// test_indicators_cpp.cpp — tests unitaires GoogleTest des indicateurs C++.
// Compilés par cpp/CMakeLists.txt (les tests restent isolés dans tests/).
#include <cmath>
#include <stdexcept>
#include <vector>

#include <gtest/gtest.h>

#include "quant/indicators.hpp"

TEST(Ema, ConvergesOnConstantSeries) {
    const std::vector<double> v(50, 5.0);
    const auto out = quant::ema(v, 10);
    EXPECT_NEAR(out.back(), 5.0, 1e-9);
    EXPECT_EQ(out.size(), v.size());
}

TEST(Rsi, HundredOnMonotonicRise) {
    std::vector<double> v(30);
    for (std::size_t i = 0; i < v.size(); ++i) v[i] = static_cast<double>(i);
    const auto out = quant::rsi(v, 14);
    EXPECT_NEAR(out.back(), 100.0, 1e-6);
}

TEST(Atr, MatchesRangeOnFlatBars) {
    const std::vector<double> high(20, 10.5);
    const std::vector<double> low(20, 9.5);
    const std::vector<double> close(20, 10.0);
    const auto out = quant::atr(high, low, close, 14);
    EXPECT_NEAR(out.back(), 1.0, 1e-6);
}

TEST(Atr, ThrowsOnMismatchedSizes) {
    const std::vector<double> a(5, 1.0);
    const std::vector<double> b(4, 1.0);
    EXPECT_THROW(quant::atr(a, b, a, 14), std::invalid_argument);
}
