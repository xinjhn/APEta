#!/usr/bin/env bash
# tools/netem.sh
# ===============
# Helper tc/netem utk sub-studi sensitivitas-jaringan (lihat audit
# METHODOLOGICAL_VERIFICATION.md). Menambah/menghapus emulasi RTT+bandwidth
# pada interface loopback (lo) -- BUKAN bagian pipeline faktorial utama,
# dipakai manual sebelum menjalankan tools/run_batch_study.py atau
# orchestrator/run_experiment.py (BASE_URL tetap 127.0.0.1, hanya latensi/
# bandwidth di jalur lo yang dibentuk).
#
# Profil mengikuti nilai TERDOKUMENTASI RESMI, bukan perkiraan:
# - fast3g : RTT=150ms, throughput=1.6Mbps down/750Kbps up -- preset
#   "Fast 3G"/"Slow 4G" Lighthouse (GoogleChrome/lighthouse, docs/throttling.md;
#   dipakai Chrome DevTools network throttling). delay 75ms PER ARAH -> RTT
#   total 2x75ms=150ms (netem delay berlaku satu arah, request DAN response
#   masing-masing kena delay).
# - slow3g : RTT=400ms, throughput=400Kbps -- preset "Slow 3G" klasik Chrome
#   DevTools (dirujuk luas pada literatur pengujian performa web). delay
#   200ms/arah -> RTT 400ms.
# - lan    : RTT~10ms -- representatif latensi intra-datacenter/co-located
#   (mis. AWS same-AZ round-trip umumnya <2ms; 10ms dipilih sbg margin aman
#   utk variasi virtualisasi/sandbox, bukan klaim presisi).
#
# Throughput RATE pada netem bersifat simetris (down=up); preset asli punya
# up berbeda (mis. fast3g up=750Kbps) -- disederhanakan krn payload respons
# (server->klien) jauh lebih besar dari request (klien->server) pada FR-01..
# FR-04 & studi batch, sehingga arah down adalah bottleneck yang relevan.
#
# PERLU root/CAP_NET_ADMIN (sudo). Selalu `clear` di akhir sesi -- qdisc
# netem PERSISTEN lintas proses sampai dihapus eksplisit atau reboot.
#
# Pakai:
#   sudo tools/netem.sh apply fast3g
#   sudo tools/netem.sh apply slow3g
#   sudo tools/netem.sh show
#   sudo tools/netem.sh clear
set -euo pipefail

IFACE="lo"
ACTION="${1:-}"
PROFILE="${2:-}"

usage() {
  echo "Usage: $0 {apply <profile>|clear|show}" >&2
  echo "Profiles: fast3g (75ms delay/arah, 1.6mbit), slow3g (200ms delay/arah, 400kbit), lan (5ms delay/arah, 100mbit)" >&2
  exit 1
}

clear_qdisc() {
  tc qdisc del dev "$IFACE" root 2>/dev/null || true
  echo "Cleared netem on $IFACE"
}

case "$ACTION" in
  apply)
    [ -z "$PROFILE" ] && usage
    clear_qdisc
    case "$PROFILE" in
      fast3g)
        tc qdisc add dev "$IFACE" root netem delay 75ms 10ms distribution normal rate 1.6mbit
        ;;
      slow3g)
        tc qdisc add dev "$IFACE" root netem delay 200ms 20ms distribution normal rate 400kbit
        ;;
      lan)
        tc qdisc add dev "$IFACE" root netem delay 5ms 1ms distribution normal rate 100mbit
        ;;
        # NB: delay 5ms/arah -> RTT~10ms, lihat catatan profil di atas modul ini.
      *)
        echo "Unknown profile: $PROFILE" >&2
        usage
        ;;
    esac
    echo "Applied profile '$PROFILE' on $IFACE:"
    tc qdisc show dev "$IFACE"
    ;;
  clear)
    clear_qdisc
    ;;
  show)
    tc qdisc show dev "$IFACE"
    ;;
  *)
    usage
    ;;
esac
