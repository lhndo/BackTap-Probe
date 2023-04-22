#!/bin/bash
KLIPPER_DIR="${HOME}/klipper"


verify_root()
{
    if [ ${UID} == '0' ]; then
    echo -e "Don't run this installation script as a root user. Exiting ..."
    exit -1
    fi
}

check_klipper()
{
    if [ ! -d "${KLIPPER_DIR}" ]; then
        echo -e "Klipper installation not found. Exiting ..."
        exit -1
    else
        echo "Klipper installation detected successfully ..."
    fi

}


link_extension()
{
    echo "Linking BackTap Probe Extension to Klipper..."
    ln -sf "${SRCDIR}/back_tap_probe.py" "${KLIPPER_DIR}/klippy/extras/back_tap_probe.py"
}

set -e

SRCDIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

verify_root
check_klipper
link_extension

echo "BackTap Probe installation complete! Enjoy!"