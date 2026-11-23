from PyInstaller.utils.hooks import collect_all, collect_delvewheel_libs_directory


datas, binaries, hiddenimports = collect_all("sentencepiece")
datas, binaries = collect_delvewheel_libs_directory("sentencepiece", datas=datas, binaries=binaries)
