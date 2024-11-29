Drawing images requires pygraphviz.

pygraphviz doesn't have pre-built wheel packages. Install it from source.

Ubuntu and Debian:
$ sudo apt-get install graphviz graphviz-dev
$ pip install pygraphviz

See: https://github.com/pygraphviz/pygraphviz/blob/main/INSTALL.txt

Windows:
- Download and install Graphviz https://gitlab.com/graphviz/graphviz/-/releases
- Add C:\<Graphviz location>\bin to PATH (with default installation path is C:\Program Files\Graphviz\bin)
- Update pip
- Run command (if Graphviz is installed to directory different from program files - specify correct path)
pip install --config-setting="--build-option=build_ext" --config-setting="--build-option=-IC:\Program Files\Graphviz\include" --config-setting="--build-option=-LC:\Program Files\Graphviz\lib" pygraphviz

If no build tools found on your system - download installer from
https://visualstudio.microsoft.com/visual-cpp-build-tools/
and install "Visual Studio SDK Build Tools Core" and "Windows 10 SDK" or "Windows 11 SDK"
