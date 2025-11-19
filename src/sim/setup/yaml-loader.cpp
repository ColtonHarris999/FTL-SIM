#include <sim/setup/yaml-loader.hpp>
#include <yaml-cpp/yaml.h>
#include <regex>
#include <stdexcept>
#include <iostream>


namespace sim::setup {

static uint64_t parse_size_field(const std::string& s) {
    static const std::regex re(R"((\d+)\s*(B|KB|K|KiB|MB|MiB|GB|GiB|TB|TiB)?)",
        std::regex::icase);

    std::smatch m;
    if (!std::regex_match(s, m, re)) {
        throw std::runtime_error("Invalid size format: " + s);
    }

    uint64_t value = std::stoull(m[1]);
    std::string unit = m[2].str();

    for (auto& c : unit) c = std::toupper(c);

    if (unit == "" || unit == "B")  return value;
    if (unit == "KB" || unit == "K")   return value * 1000ULL;
    if (unit == "KIB")                 return value * 1024ULL;
    if (unit == "MB")                  return value * 1000ULL * 1000ULL;
    if (unit == "MIB")                 return value * 1024ULL * 1024ULL;
    if (unit == "GB")                  return value * 1000ULL * 1000ULL * 1000ULL;
    if (unit == "GIB")                 return value * 1024ULL * 1024ULL * 1024ULL;
    if (unit == "TB")                  return value * 1000ULL * 1000ULL * 1000ULL * 1000ULL;
    if (unit == "TIB")                 return value * 1024ULL * 1024ULL * 1024ULL * 1024ULL;

    throw std::runtime_error("Unknown size unit: " + unit);
}

static EccType parse_ecc(const std::string& s) {
    std::string up = s;
    for (auto& c : up) c = std::toupper(c);

    if (up == "NONE") return EccType::None;
    if (up == "BCH")  return EccType::BCH;
    if (up == "LDPC") return EccType::LDPC;
    throw std::runtime_error("Invalid ECC type: " + s);
}

static MappingGranularity parse_mapping(const std::string& s) {
    std::string up = s;
    for (auto& c : up) c = std::toupper(c);

    if (up == "BLOCK")   return MappingGranularity::Block;
    if (up == "PAGE")    return MappingGranularity::Page;
    if (up == "SUBPAGE") return MappingGranularity::SubPage;
    throw std::runtime_error("Invalid mapping granularity: " + s);
}

SetupConfig load_ssd_config(const std::string& path) {
    YAML::Node root = YAML::LoadFile(path);
    SetupConfig cfg{};

    auto P = root["physical"];
    cfg.bits_per_cell   = P["bits_per_cell"].as<std::uint32_t>();
    cfg.bytes_per_page  = parse_size_field(P["bytes_per_page"].as<std::string>());
    cfg.pages_per_block = P["pages_per_block"].as<std::uint32_t>();
    cfg.blocks_per_plane = P["blocks_per_plane"].as<std::uint32_t>();
    cfg.planes_per_die   = P["planes_per_die"].as<std::uint32_t>();
    cfg.dies_per_package = P["dies_per_package"].as<std::uint32_t>();
    cfg.packages         = P["packages"].as<std::uint32_t>();

    auto E = root["ecc"];
    cfg.ecc_type        = parse_ecc(E["type"].as<std::string>());
    cfg.ecc_bits_per_1k = E["bits_per_1k"].as<std::uint32_t>();

    auto D = root["dram"];
    cfg.dram_bytes      = parse_size_field(D["total_bytes"].as<std::string>());
    cfg.fast_ftl_bytes  = parse_size_field(D["fast_ftl_bytes"].as<std::string>());

    auto M = root["mapping"];
    cfg.base_mapping      = parse_mapping(M["base_granularity"].as<std::string>());
    cfg.fast_mapping      = parse_mapping(M["fast_granularity"].as<std::string>());
    cfg.subpages_per_page = M["subpages_per_page"].as<std::uint32_t>();

    return cfg;
}

} // namespace sim::setup
