import pytest

from aula_f108 import device


def add_hidraw(root, node, vendor, product, iface):
    """Fake just enough of sysfs for one hidraw node."""
    usb_if = root / "devices" / f"usb-{node}" / f"1-1:1.{iface}"
    hid = usb_if / f"0003:{vendor:04X}:{product:04X}.0001"
    hid.mkdir(parents=True)
    (usb_if / "bInterfaceNumber").write_text(f"{iface:02x}\n")
    (hid / "uevent").write_text(
        f"DRIVER=hid-generic\nHID_ID=0003:{vendor:08X}:{product:08X}\n")
    cls = root / "class"
    (cls / node).mkdir(parents=True)
    (cls / node / "device").symlink_to(hid)
    return str(cls)


def test_finds_config_interface(tmp_path):
    for i in range(4):
        sysfs = add_hidraw(tmp_path, f"hidraw{i}", 0x0C45, 0x800A, i)
    add_hidraw(tmp_path, "hidraw9", 0x046D, 0xC336, 0)
    assert device.find(sysfs) == "/dev/hidraw3"


def test_dongle_only(tmp_path):
    sysfs = add_hidraw(tmp_path, "hidraw5", 0x05AC, 0x024F, 3)
    with pytest.raises(device.NotFound, match="receiver"):
        device.find(sysfs)


def test_nothing_connected(tmp_path):
    sysfs = add_hidraw(tmp_path, "hidraw0", 0x046D, 0xC336, 0)
    with pytest.raises(device.NotFound, match="not found"):
        device.find(sysfs)


def test_ioctl_numbers():
    # HIDIOCSFEATURE(65) / HIDIOCGFEATURE(65) from linux/hidraw.h
    assert device._set_feature(65) == 0xC0414806
    assert device._get_feature(65) == 0xC0414807
