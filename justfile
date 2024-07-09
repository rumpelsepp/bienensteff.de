deploy:
    hugo && rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de
