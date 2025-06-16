build: clean
    npm run build
    podman run \
        --net=none \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD" \
        --workdir "/mnt/$PWD" \
        --userns keep-id \
        --group-add keep-groups \
        --log-driver none \
        ghcr.io/gohugoio/hugo:latest \
        build \
        --ignoreCache

deploy: build
     rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

podman-pull:
    podman pull ghcr.io/gohugoio/hugo:latest

serve: clean
    npm run build
    podman run \
        --net=host \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD" \
        --workdir "/mnt/$PWD" \
        --userns keep-id \
        --group-add keep-groups \
        --log-driver none \
        ghcr.io/gohugoio/hugo:latest \
        server \
        --ignoreCache

clean:
    rm -rf public

update-db:
    ./scripts/dump-db-sql.py > assets/db/db.json

update-trachtnet:
    ./scripts/gen-trachtnet.py --from-year $(date -d "last year" +%Y) --name Bayern --region bayern
    mv -f trachtnet-bayern.svg static/trachtnet/trachtnet-bayern-current.svg
    ./scripts/gen-trachtnet.py --from-year $(date +%Y) --name Bayern --region bayern --derivative
    mv -f trachtnet-bayern-derivative.svg static/trachtnet/trachtnet-bayern-current-derivative.svg
    
    ./scripts/gen-trachtnet.py --name Bayern --region bayern
    ./scripts/gen-trachtnet.py --name Oberbayern --region oberbayern
    ./scripts/gen-trachtnet.py --station-id 1276 --name "Dr. Gerhard Liebig (Waage 1276)"

    mv -f trachtnet-*.svg static/trachtnet/
    
update-trachtnet-chosen:
    ./scripts/gen-trachtnet.py --chosen-evaluations
    mv -f *.svg static/trachtnet/
