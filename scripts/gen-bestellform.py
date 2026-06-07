#!/usr/bin/env -S uv run -s

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "jinja2>=3.1.6",
# ]
# ///

import json
import sys
import jinja2

TPL = """
<div class="row g-3 mb-3">
    <div class="card col-md-8">
        <div class="card-body">
            <form method="post" action="https://forms.bienensteff.de/submit/order">
                <label class="form-label" for="name">Name*</label>
                <input type="text" class="form-control" id="name" name="name" required>
                <div class="form-text mb-3">
                    Mit welchem Namen dürfen wir Dich ansprechen?
                </div>

                <label class="form-label" for="email">E-Mail*</label>
                <input type="email" class="form-control" id="email" name="email" required>
                <div class="form-text mb-3">
                    An diese E-Mail Adresse bekommst Du eine Antwort von uns.
                </div>

                <label class="form-label" for="phone">Telefon</label>
                <input type="tel" class="form-control" id="phone" name="phone">
                <div class="form-text mb-3">
                    An diese Telefonnummer wenden wir uns nur bei Rückfragen.
                </div>
                
                {% for article in articles %}
                    {% if article.in_stock %}
                        <div class="row">
                            <label class="form-check-label" for="{{ article.sku }}">
                                {% raw %}{{ if hugo.IsDevelopment }}{% endraw %}
                                    <a href="/datenbank/q/sku-{{ article.sku | lower }}">{{ article.label }}</a>
                                {% raw %}{{ else }}{% endraw %}
                                    <a href="https://db.bienensteff.de?q=sku-{{ article.sku | lower }}">{{ article.label }}</a>
                                {% raw %}{{ end }}{% endraw %}

                            </label>
                            <div class="col-md-2">
                                <input type="number" class="form-control" id="{{ article.sku }}" name="{{ article.sku }}" value="0" min="0">
                            </div>
                            <div class="form-text mb-3">
                                Einzelpreis: {{ article.price }} € ({{ article.price_per_kg }} € / kg)
                            </div>
                        </div>
                    {% endif %}
                {% endfor %}

                <div class="mb-3">
                    <label class="form-label" for="delivery">Versand</label>
                    <select class="form-select" id="delivery" name="delivery">
                        <option value="Abholung (Gräfelfinger Str. 169a, 81375 München)" selected>Abholung (Gräfelfinger Str. 169a, 81375 München)</option>
                        <option value="Abholung (Granitweg 20, 94481 Grafenau)">Abholung (Granitweg 20, 94481 Grafenau)</option>
                        <option value="kostenlose Lieferung (nur im Umkreis Hadern!)">kostenlose Lieferung (nur im Umkreis Hadern!)</option>
                        <option value="Postversand (zzgl. Frachtkosten)">Postversand (zzgl. Frachtkosten)</option>
                    </select>
                <div class="form-text mb-3">
                    Wie möchtest du Deine Ware erhalten?
                </div>
                </div>

                <div class="mb-3">
                    <label class="form-label" for="comment">Nachricht</label>
                    <textarea class="form-control" id="comment" name="comment" rows="4"></textarea>
                    <div class="form-text">
                        Hast du Sonderwünsche oder möchtest Du uns noch etwas mitteilen?
                    </div>
                </div>

                <div class="mb-3">
                    <button class="btn btn-primary" type="submit">unverbindliche Anfrage senden</button>
                </div>
            </form>
        </div>
    </div>
</div>
"""

def main():
    pricelist = json.loads(sys.stdin.read())

    out = (jinja2.Environment(
        trim_blocks=True,
        autoescape=False,
    )
    .from_string(TPL)
    .render(pricelist)
    .strip()    
    )
    print(out)

if __name__ == "__main__":
    main()
