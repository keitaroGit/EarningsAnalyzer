f = open('templates/index.html', 'r', encoding='utf-8').read()
f = f.replace(
    '<div class="disclaimer-box" id="res-disclaimer"></div>\n\n      <!-- Charts -->',
    '<!-- Charts -->'
)
f = f.replace(
    '</div>\n    </div>\n  </div>',
    '</div>\n      <div class="disclaimer-box" id="res-disclaimer"></div>\n    </div>\n  </div>'
)
open('templates/index.html', 'w', encoding='utf-8').write(f)
print('done')