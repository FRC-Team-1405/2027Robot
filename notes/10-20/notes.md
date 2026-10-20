i need to determine:
- if orange pi's the best coprocessor to invest in
- i think our camera is the best camera for cheap coverage, but can we get a high quality camera for longer distance/high accuracy (high res) targeting
- is there significant performance improvements running one camera per orange pi vs two camera's per orange pi

# Bootstrap OrangePi Error

PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1
Bootstrap-OrangePi 2026-10-18.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Looking for a Pi (mDNS name, the ICS 192.168.137.x subnet, and the bench address)...
         No 192.168.137.x adapter on this laptop, so Internet Connection Sharing is probably off.
  [PASS] Found a Pi at p

==============================================================================
Step 3/11: SSH key login
==============================================================================
  Why:  Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.
  Doing: No key at C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi - creating a new ed25519 key with no passphrase (it is only used for this Pi).
  ? Create it? [Y/n]: y
  [FAIL] ssh-keygen failed: Too many arguments.
usage: ssh-keygen [-q] [-a rounds] [-b bits] [-C comment] [-f output_keyfile]
                  [-m format] [-N new_passphrase] [-O option]
                  [-t dsa | ecdsa | ecdsa-sk | ed25519 | ed25519-sk | rsa]
                  [-w provider] [-Z cipher]
       ssh-keygen -p [-a rounds] [-f keyfile] [-m format] [-N new_passphrase]
                   [-P old_passphrase] [-Z cipher]
       ssh-keygen -i [-f input_keyfile] [-m key_format]
       ssh-keygen -e [-f input_keyfile] [-m key_format]
       ssh-keygen -y [-f input_keyfile]
       ssh-keygen -c [-a rounds] [-C comment] [-f keyfile] [-P passphrase]
       ssh-keygen -l [-v] [-E fingerprint_hash] [-f input_keyfile]
       ssh-keygen -B [-f input_keyfile]
       ssh-keygen -D pkcs11
       ssh-keygen -F hostname [-lv] [-f known_hosts_file]
       ssh-keygen -H [-f known_hosts_file]
       ssh-keygen -K [-a rounds] [-w provider]
       ssh-keygen -R hostname [-f known_hosts_file]
       ssh-keygen -r hostname [-g] [-f input_keyfile]
       ssh-keygen -M generate [-O option] output_file
       ssh-keygen -M screen [-f input_file] [-O option] output_file
       ssh-keygen -I certificate_identity -s ca_key [-hU] [-D pkcs11_provider]
                  [-n principals] [-O option] [-V validity_interval]
                  [-z serial_number] file ...
       ssh-keygen -L [-f input_keyfile]
       ssh-keygen -A [-a rounds] [-f prefix_path]
       ssh-keygen -k -f krl_file [-u] [-s ca_public] [-z version_number]
                  file ...
       ssh-keygen -Q [-l] -f krl_file [file ...]
       ssh-keygen -Y find-principals -s signature_file -f allowed_signers_file
       ssh-keygen -Y match-principals -I signer_identity -f allowed_signers_file
       ssh-keygen -Y check-novalidate -n namespace -s signature_file
       ssh-keygen -Y sign -f key_file -n namespace file [-O option] ...
       ssh-keygen -Y verify -f allowed_signers_file -I signer_identity
                  -n namespace -s signature_file [-r krl_file] [-O option]


  [FAIL] Could not create key.

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  PASS    Find the Pi                p
   3  FAIL    SSH key                    keygen failed

  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.
         Pi: pi@p   key: C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
         Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).
         When done with the Pi, switch Internet Connection Sharing off again.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1 --usage
Bootstrap-OrangePi 2026-10-18.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Checking the address you gave: --usage
  [FAIL] Nothing answers on port 22 at --usage.

  [FAIL] Pi not reachable at --usage. Check power, cable, and that the laptop and Pi share a network.

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  FAIL    Find the Pi                no SSH at --usage

  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1 photonvision.local
Bootstrap-OrangePi 2026-10-18.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Checking the address you gave: photonvision.local
  [PASS] SSH answers at photonvision.local

==============================================================================
Step 3/11: SSH key login
==============================================================================
  Why:  Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.
  Doing: No key at C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi - creating a new ed25519 key with no passphrase (it is only used for this Pi).
  ? Create it? [Y/n]: y
  [FAIL] ssh-keygen failed: Too many arguments.
usage: ssh-keygen [-q] [-a rounds] [-b bits] [-C comment] [-f output_keyfile]
                  [-m format] [-N new_passphrase] [-O option]
                  [-t dsa | ecdsa | ecdsa-sk | ed25519 | ed25519-sk | rsa]
                  [-w provider] [-Z cipher]
       ssh-keygen -p [-a rounds] [-f keyfile] [-m format] [-N new_passphrase]
                   [-P old_passphrase] [-Z cipher]
       ssh-keygen -i [-f input_keyfile] [-m key_format]
       ssh-keygen -e [-f input_keyfile] [-m key_format]
       ssh-keygen -y [-f input_keyfile]
       ssh-keygen -c [-a rounds] [-C comment] [-f keyfile] [-P passphrase]
       ssh-keygen -l [-v] [-E fingerprint_hash] [-f input_keyfile]
       ssh-keygen -B [-f input_keyfile]
       ssh-keygen -D pkcs11
       ssh-keygen -F hostname [-lv] [-f known_hosts_file]
       ssh-keygen -H [-f known_hosts_file]
       ssh-keygen -K [-a rounds] [-w provider]
       ssh-keygen -R hostname [-f known_hosts_file]
       ssh-keygen -r hostname [-g] [-f input_keyfile]
       ssh-keygen -M generate [-O option] output_file
       ssh-keygen -M screen [-f input_file] [-O option] output_file
       ssh-keygen -I certificate_identity -s ca_key [-hU] [-D pkcs11_provider]
                  [-n principals] [-O option] [-V validity_interval]
                  [-z serial_number] file ...
       ssh-keygen -L [-f input_keyfile]
       ssh-keygen -A [-a rounds] [-f prefix_path]
       ssh-keygen -k -f krl_file [-u] [-s ca_public] [-z version_number]
                  file ...
       ssh-keygen -Q [-l] -f krl_file [file ...]
       ssh-keygen -Y find-principals -s signature_file -f allowed_signers_file
       ssh-keygen -Y match-principals -I signer_identity -f allowed_signers_file
       ssh-keygen -Y check-novalidate -n namespace -s signature_file
       ssh-keygen -Y sign -f key_file -n namespace file [-O option] ...
       ssh-keygen -Y verify -f allowed_signers_file -I signer_identity
                  -n namespace -s signature_file [-r krl_file] [-O option]


  [FAIL] Could not create key.

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  PASS    Find the Pi                photonvision.local
   3  FAIL    SSH key                    keygen failed

  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.
         Pi: pi@photonvision.local   key: C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
         Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).
         When done with the Pi, switch Internet Connection Sharing off again.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor>