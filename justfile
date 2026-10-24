# The recipes every site shares (npm-build, build, serve, clean,
# podman-pull, check-links); a recipe below under the same name replaces
# the theme's.
import 'themes/bienensteff/justfile'

# For the recipes here that replace one of the theme's.
set allow-duplicate-recipes

# List all recipes
default:
    @just --list --unsorted

# bscli lives in its own repository: a checkout next to this one if there
# is one (for working on both), else uvx fetches it from GitHub (CI).
# $BSCLI overrides both.
bscli_checkout := justfile_directory() / ".." / "bscli"
bscli := env("BSCLI", if path_exists(bscli_checkout / "pyproject.toml") == "true" {
    "uv run --project " + bscli_checkout + " bscli"
} else {
    "uvx --from git+https://github.com/rumpelsepp/bscli bscli"
})

build: npm-build
    {{ hugo }} build --cleanDestinationDir

deploy: build
    rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

update-db:
    {{ bscli }} dump db > assets/db/db.json

update-trachtnet:
    {{ bscli }} dump trachtnet --outdir static/trachtnet-dump
    {{ bscli }} dump trachtnet-summary --outdir static/trachtnet-dump

update-klima:
    {{ bscli }} dump dwd --station-id 03379 --since-year 2011 --meta static/klima/03379_meta.json static/klima/03379_hourly.json static/klima/03379_daily.json
