import pytest
from src.ui.runtime import check_tk_version

@pytest.mark.parametrize('version', ['8.5.9', '8.6.8', '8.6.10'])
def test_reject_obsolete_macos_tk(version):
    with pytest.raises(RuntimeError, match='too old'):
        check_tk_version(version, 'Darwin')

@pytest.mark.parametrize('version', ['8.6.11', '8.6.14', '8.6.16', '9.0.0'])
def test_supported_macos_tk(version):
    check_tk_version(version, 'Darwin')

def test_mac_gate_does_not_block_windows():
    check_tk_version('8.6.10', 'Windows')
