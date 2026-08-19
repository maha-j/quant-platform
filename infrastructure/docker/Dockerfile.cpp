# Build + test du cœur C++ (libquant) de façon reproductible.
# Étape unique : compile la lib, la DLL/so exportable et exécute GoogleTest.
FROM ubuntu:24.04 AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git libfmt-dev libspdlog-dev libeigen3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
# Le contexte de build doit être la racine du dépôt (les tests sont dans tests/).
COPY cpp/ ./cpp/
COPY tests/ ./tests/

RUN cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DQUANT_BUILD_TESTS=ON \
    && cmake --build build -j"$(nproc)" \
    && ctest --test-dir build --output-on-failure

# Image finale : n'expose que les artefacts binaires (DLL/so).
FROM ubuntu:24.04
COPY --from=build /src/build/libquant.so /opt/quant/lib/
