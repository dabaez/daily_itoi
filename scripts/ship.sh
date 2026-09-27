#!/usr/bin/env bash
# Publishes the site to the droplet. deploy.yml runs this, and so can you from
# your own machine:
#
#   DEPLOY_TARGET=darling-deploy scripts/ship.sh           # upload a release
#   DEPLOY_TARGET=darling-deploy scripts/ship.sh build     # run the daily job now (doesn't wait)
#   DEPLOY_TARGET=darling-deploy scripts/ship.sh rollback  # previous release goes live
#   DEPLOY_TARGET=darling-deploy scripts/ship.sh activate <release-id>
#   DEPLOY_TARGET=darling-deploy scripts/ship.sh releases  # list releases, * is live
#
# DEPLOY_TARGET is darling@<droplet> or a Host alias from ~/.ssh/config. On
# the droplet the key can only run receive-site (dabaez/droplet-infra).
#
# web/ has no build step and loads today.json at runtime, so the daily job
# isn't part of a deploy: it runs on the droplet on its own timer
# (deploy/systemd/). Each release uploads:
#
#   public/   the committed web/, with two links to the site user's home,
#             outside releases:
#               today.json -> ~/published/today.json  (written by the job)
#               art        -> ~/published/art         (the real sprites and
#                                                     font, never in git)
#   app/      the repo, so the timer can run builder/ and receive-site can
#             install deploy/systemd/
set -euo pipefail

TARGET="${DEPLOY_TARGET:?set DEPLOY_TARGET, e.g. darling@<droplet> or an ssh config alias}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."

remote() {
  ssh -o BatchMode=yes "$TARGET" "$@"
}

case "${1:-}" in
"") ;;
build)
  remote start darling-build.service
  exit
  ;;
rollback | releases)
  remote "$1"
  exit
  ;;
activate)
  remote activate "${2:?usage: ship.sh activate <release-id>}"
  exit
  ;;
*)
  echo "usage: ship.sh [build | rollback | releases | activate <release-id>]" >&2
  exit 1
  ;;
esac

# A release is a commit: refuse to publish anything that isn't committed.
if [ -n "$(git status --porcelain)" ]; then
  echo "uncommitted changes; commit or stash them before shipping:" >&2
  git status --short >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# From git, not the working tree, so a local web/today.json or web/art/ never ships.
git archive HEAD web | tar -x -C "$STAGE"
mv "$STAGE/web" "$STAGE/public"
# From releases/<id>/public/, the site user's home is ../../../
ln -s ../../../published/today.json "$STAGE/public/today.json"
ln -s ../../../published/art "$STAGE/public/art"
git archive --prefix=app/ HEAD | tar -x -C "$STAGE"

id="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short=12 HEAD)"
echo "--- shipping $id to $TARGET"
tar -czf - -C "$STAGE" public app | remote deploy "$id"
