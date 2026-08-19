// pybind_module.cpp — expose libquant à Python sous le nom `quant_native`.
//
// Interopérabilité Python : les np.ndarray sont convertis en std::span sans copie
// superflue ; le résultat std::vector<double> est renvoyé comme numpy array.
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "quant/indicators.hpp"

namespace py = pybind11;

namespace {

// Vue non-propriétaire sur un array numpy contigu de double.
std::span<const double> as_span(const py::array_t<double>& a) {
    const auto buf = a.request();
    return {static_cast<const double*>(buf.ptr), static_cast<std::size_t>(buf.size)};
}

}  // namespace

PYBIND11_MODULE(quant_native, m) {
    m.doc() = "Indicateurs quant haute performance (C++20).";

    m.def("ema", [](const py::array_t<double>& v, std::size_t p) {
        return quant::ema(as_span(v), p);
    }, py::arg("values"), py::arg("period"));

    m.def("rsi", [](const py::array_t<double>& c, std::size_t p) {
        return quant::rsi(as_span(c), p);
    }, py::arg("close"), py::arg("period") = 14);

    m.def("atr", [](const py::array_t<double>& h, const py::array_t<double>& l,
                    const py::array_t<double>& c, std::size_t p) {
        return quant::atr(as_span(h), as_span(l), as_span(c), p);
    }, py::arg("high"), py::arg("low"), py::arg("close"), py::arg("period") = 14);
}
