deploy: clean
     podman run \
        --net=none \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD" \
        --workdir "/mnt/$PWD" \
        --userns keep-id \
        --group-add keep-groups \
        --log-driver none \\
        ghcr.io/gohugoio/hugo:latest \
        build \
        --ignoreCache && \
     rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

podman-pull:
    podman pull ghcr.io/gohugoio/hugo:latest

serve: clean
     podman run \
        --net=host \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD" \
        --workdir "/mnt/$PWD" \
        --userns keep-id \
        --group-add keep-groups \
        --log-driver none \\
        ghcr.io/gohugoio/hugo:latest \
        server \
        --ignoreCache

clean:
    rm -rf public

update-db:
    ./scripts/dump-db-sql.py > assets/db/db.json
