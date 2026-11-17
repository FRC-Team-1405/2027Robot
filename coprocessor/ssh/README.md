# Team SSH key for the Orange Pis

`id_ed25519_orangepi` is the key every team laptop uses to log in to the robot's Orange Pis as
`pi`. It's committed on purpose, so a new laptop can reach the Pis without anyone typing the Pi
password.

**You don't need to do anything with it.** `Bootstrap-OrangePi.ps1` copies it to
`%USERPROFILE%\.ssh\id_ed25519_orangepi` the first time it runs on a laptop that doesn't have
that file yet, and locks the copy down so Windows OpenSSH accepts it. The `sim\` scripts and
plain `ssh -i ~/.ssh/id_ed25519_orangepi pi@LeftPi.local` then use the same file. A laptop that
already has its own `id_ed25519_orangepi` keeps it; bootstrap installs it on the Pi as before.

## Why it's OK in a public repo

- The Pis have no Wi-Fi. They are reachable only on the robot's own network (or a laptop plugged
  straight into one), and they run nothing but vision processing.
- The `pi` password is already in this repo (`tools/logbench/server/remote_config.json`), so the
  key gives nobody access they don't already have.

**Use this key only for the Orange Pis.** Don't add its public half anywhere else (GitHub, the
roboRIO, a home server), and don't put any other key in this folder. Keep laptop-specific keys
such as `~/.ssh/id_ed25519` out of the repo.

## If it ever needs replacing

Run `ssh-keygen -t ed25519 -N "" -C orangepi-team -f coprocessor\ssh\id_ed25519_orangepi`, commit
both files, then on each Pi replace the old line in `~pi/.ssh/authorized_keys` with the new
`.pub` line (bootstrap does this for you if you type the Pi password once when it asks). Delete
`%USERPROFILE%\.ssh\id_ed25519_orangepi` on each laptop so bootstrap copies the new one.
