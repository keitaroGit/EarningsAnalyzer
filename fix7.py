f = open('templates/index.html', 'r', encoding='utf-8').read()
old = '      <div class="disclaimer-box" id="res-disclaimer"></div>\n\n      <!-- Charts -->'
new = '      <!-- Charts -->'
f = f.replace(old, new)

old2 = '      <div class="next-earnings-box" id="next-earnings-box">\n        <span class="next-earnings-label">📅 Next Earnings Date</span>\n        <span class="next-earnings-date" id="next-earnings-date"></span>\n      </div>\n    </div>'
new2 = '      <div class="next-earnings-box" id="next-earnings-box">\n        <span class="next-earnings-label">📅 Next Earnings Date</span>\n        <span class="next-earnings-date" id="next-earnings-date"></span>\n      </div>\n      <div class="disclaimer-box" id="res-disclaimer"></div>\n    </div>'
f = f.replace(old2, new2)

open('templates/index.html', 'w', encoding='utf-8').write(f)
print('done')