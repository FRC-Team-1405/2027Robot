"""What each Orange Pi's Ethernet link is doing right now: speed, duplex, errors, and what the OTHER end offers.

    python -m exprunner link              # every Pi in coprocessor/robots.json
    python -m exprunner link --board LeftPi

Over SSH, read-only. For a Pi running at 100 Mbit/s when its twin runs at 1000, the useful line is the last one: when two
ends of a cable meet, each says which speeds it can do and they use the best they have in common. So:

  * the far end (switch / radio port / the other device) only offers 10/100  -> that port or device is the limit;
  * both ends offer 1000 but the link came up at 100                         -> the cable (or a connector) can't carry
    all four pairs, which gigabit needs and 100 Mbit does not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Run on the Pi: every wired interface, from /sys (no root needed), then ethtool for what each end advertises.
SCRIPT = r"""
for i in /sys/class/net/e*; do
  n=$(basename "$i")
  echo "IF $n"
  for f in operstate speed duplex carrier_changes; do echo "$f=$(cat "$i/$f" 2>/dev/null)"; done
  for f in rx_errors rx_dropped tx_errors rx_crc_errors; do echo "$f=$(cat "$i/statistics/$f" 2>/dev/null)"; done
  ethtool "$n" 2>/dev/null | sed 's/^/ETHTOOL /'
done
"""


@dataclass
class Link:
    name: str
    values: dict[str, str] = field(default_factory=dict)
    ethtool: list[str] = field(default_factory=list)

    @property
    def speed(self) -> int | None:
        try:
            v = int(self.values.get("speed", ""))
        except ValueError:
            return None
        return v if v > 0 else None

    def modes(self, header: str) -> set[int]:
        """The speeds (Mbit/s) listed under one ethtool heading, e.g. 'Link partner advertised link modes'."""
        out: set[int] = set()
        grabbing = False
        for raw in self.ethtool:
            line = raw.rstrip()
            m = re.match(rf"^\s*{re.escape(header)}:\s*(.*)$", line)
            if m:
                grabbing = True
                out |= _speeds(m.group(1))
                continue
            if grabbing:
                if re.match(r"^\s+\S", line) and not re.match(r"^\s*[A-Z][A-Za-z -]+:", line):
                    out |= _speeds(line)
                else:
                    grabbing = False
        return out

    def summary(self) -> str:
        v = self.values
        if v.get("operstate") != "up":
            return f"{self.name}: {v.get('operstate') or 'unknown'} (no link)"
        spd = f"{self.speed} Mbit/s" if self.speed else "speed unknown"
        text = f"{self.name}: up, {spd}, {v.get('duplex') or '?'} duplex, {v.get('carrier_changes') or '?'} carrier change(s)"
        errs = {k: v.get(k) for k in ("rx_errors", "rx_dropped", "tx_errors", "rx_crc_errors") if v.get(k) not in (None, "", "0")}
        if errs:
            text += ", " + ", ".join(f"{k} {n}" for k, n in errs.items())
        return text

    def verdict(self) -> str:
        """Where the limit probably is, from what each end advertises. Empty if there is nothing to say."""
        if not self.speed or self.speed >= 1000:
            return ""
        mine, partner = self.modes("Advertised link modes"), self.modes("Link partner advertised link modes")
        if not mine:
            return "ethtool gave no advertised modes (not installed? try `sudo apt install ethtool` on the Pi)."
        if 1000 not in mine:
            return "this Pi's port is not advertising 1000 (auto-negotiation was changed?)."
        if not partner:
            return "the other end advertised nothing we could read."
        if 1000 not in partner:
            return (f"the OTHER END offers at most {max(partner)} Mbit/s: its port, or the device behind it, is the limit "
                    "(try another port on the radio/switch).")
        return ("both ends advertise 1000 but the link is at 100: the cable (or a connector) is the likely limit, "
                "because gigabit needs all four wire pairs and 100 Mbit needs only two. Try another cable.")


def _speeds(text: str) -> set[int]:
    return {int(m.group(1)) for m in re.finditer(r"(\d+)base", text)}


def parse(output: str) -> list[Link]:
    links: list[Link] = []
    for line in output.splitlines():
        if line.startswith("IF "):
            links.append(Link(line[3:].strip()))
        elif links and line.startswith("ETHTOOL "):
            links[-1].ethtool.append(line[len("ETHTOOL "):])
        elif links and "=" in line:
            k, _, val = line.partition("=")
            links[-1].values[k.strip()] = val.strip()
    return links


def check(pi) -> list[Link]:
    """Read one Pi's wired interfaces (pi is an exprunner.remote.Pi)."""
    return parse(pi.check(SCRIPT))
