;; To run: guix shell --preserve=OAR* --pure -m manifest-pip.scm
;; then: source .venv/bin/activate
;; if the .venv doesnt exist:
;; python -m venv .venv 
;; source .venv/bin/activate 
;; pip install -r requirements.txt

;;(specifications->manifest (list "wget" "netcdf" "hdf5" "openmpi" "vim" "gcc-toolchain" "git" "coreutils" "tcl" "pkg-config" "zlib" "python" "python-h5py" "python-numpy"))
;; manifest.scm
(use-modules (guix build-system gnu)
	     (ice-9 match))

(define stdenv
  (map (lambda* (pkg)
		(match pkg
		       ((_ value _ ...)
			value)))
       (standard-packages)))
(concatenate-manifests
  (list
    (specifications->manifest
      (list
	"bash"
	"gcc-toolchain"
	"gfortran-toolchain"
	"cmake"
	"wget" 
	"netcdf-parallel-openmpi" 
	"hdf5-parallel-openmpi" 
	"openmpi@4.1.6" 
	"vim" 
	"git" 
	"tcl" 
	"pkg-config" 
	"zlib" 
	"python-next" 
	"which"
	"curl"
	"libyaml"
	"openssh"
	"less"
	"procps"
	"psmisc"
	))
    (packages->manifest stdenv)))

;; After starting guix shell --pure -m thisfile.scm 
;; create a venv with python3 -m venv .venv 
;; then run 
;; pip install -r requirements.txt
