from exprunner import link

LEFT = """IF end1
operstate=up
speed=100
duplex=full
carrier_changes=1
rx_errors=0
rx_dropped=0
tx_errors=0
rx_crc_errors=0
ETHTOOL Settings for end1:
ETHTOOL \tSupported link modes:   10baseT/Half 10baseT/Full
ETHTOOL \t                        100baseT/Half 100baseT/Full
ETHTOOL \t                        1000baseT/Full
ETHTOOL \tSupported pause frame use: Symmetric Receive-only
ETHTOOL \tAdvertised link modes:  10baseT/Half 10baseT/Full
ETHTOOL \t                        100baseT/Half 100baseT/Full
ETHTOOL \t                        1000baseT/Full
ETHTOOL \tAdvertised pause frame use: Symmetric Receive-only
ETHTOOL \tLink partner advertised link modes:  10baseT/Half 10baseT/Full
ETHTOOL \t                                     100baseT/Half 100baseT/Full
ETHTOOL \tLink partner advertised pause frame use: Symmetric
ETHTOOL \tSpeed: 100Mb/s
"""


def one(text):
    return link.parse(text)[0]


def test_parse_values_and_modes():
    lk = one(LEFT)
    assert lk.name == "end1" and lk.speed == 100 and lk.values["duplex"] == "full"
    assert lk.modes("Advertised link modes") == {10, 100, 1000}
    assert lk.modes("Link partner advertised link modes") == {10, 100}
    assert "up, 100 Mbit/s, full duplex, 1 carrier change" in lk.summary()


def test_the_other_end_limiting_the_link_is_named():
    assert "OTHER END offers at most 100" in one(LEFT).verdict()


def test_a_cable_limit_is_named_when_both_ends_offer_gigabit():
    both = LEFT.replace("Link partner advertised link modes:  10baseT/Half 10baseT/Full\nETHTOOL \t                                     100baseT/Half 100baseT/Full",
                        "Link partner advertised link modes:  10baseT/Half 10baseT/Full 100baseT/Half 100baseT/Full 1000baseT/Full")
    assert "the cable (or a connector)" in one(both).verdict()


def test_a_gigabit_link_has_nothing_to_explain_and_errors_show():
    fast = LEFT.replace("speed=100", "speed=1000").replace("rx_crc_errors=0", "rx_crc_errors=12")
    lk = one(fast)
    assert lk.verdict() == "" and "rx_crc_errors 12" in lk.summary()


def test_no_link_and_no_ethtool():
    down = one("IF end1\noperstate=down\nspeed=-1\n")
    assert down.speed is None and "no link" in down.summary() and down.verdict() == ""
    noeth = one("IF end1\noperstate=up\nspeed=100\nduplex=full\n")
    assert "no advertised modes" in noeth.verdict()


def test_check_runs_the_script_on_the_pi():
    class P:
        def check(self, cmd):
            assert "/sys/class/net/e*" in cmd and "ethtool" in cmd
            return LEFT
    assert link.check(P())[0].speed == 100
