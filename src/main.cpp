#include "yaml-loader.hpp"
#include "ftl-layout.hpp"

int main() {
    try {
        SsdConfig cfg = load_ssd_config("ssd_config.yaml");
        FtlLayout layout(cfg);

        layout.print_summary();
    }
    catch (const std::exception& e) {
        std::cerr << "Config error: " << e.what() << "\n";
        return 1;
    }
}
