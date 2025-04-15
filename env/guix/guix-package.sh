#!/bin/bash

set +xeu
BASE_ROOTDIR=$(dirname $(dirname $(dirname $(readlink -f "${BASH_SOURCE[0]}"))))
PROFILE=$BASE_ROOTDIR/env/guix/profile

guix package -m "$BASE_ROOTDIR"/env/guix/manifest-pip.scm --profile="$PROFILE"
set -xeu