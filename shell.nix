let
  pkgs =
    import
    (
      fetchTarball "https://github.com/NixOS/nixpkgs/archive/3a3b818fe26054cea25e9895a86ff3559c218510.tar.gz"
    ) {};

  myPython = pkgs.python3;
in
  pkgs.mkShell {
    packages = [
      # need the python packages
      (myPython.withPackages (pp: [
        pp.plotly
        pp.pandas
        pp.numpy
      ]))
    ];
  }
