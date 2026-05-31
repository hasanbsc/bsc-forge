// 2D Oyun Stüdyosu — elle doğrulanmış Kaplay oyun şablonları.
//
// Küçük yerel model (qwen2.5-coder:3b) sıfırdan oyun üretmede tutarsız ama bir
// oyunu DÜZENLEMEDE güvenilir. Bu yüzden yaygın türlerde modele sıfırdan değil,
// aşağıdaki çalışan oyunlardan birini "temel al ve uyarla" görevi veriyoruz
// (ChatWindow tohumlaması). Model bozarsa güvenlik ağı şablonun kendisine düşer.
//
// Her şablon tek dosyalık, çarpışan tüm nesnelerde area() olan, görünür paletli,
// kontrol yazısı gerçek tuşlarla tutarlı, skor + "Oyun Bitti" + BOŞLUK restart
// içeren TAM bir oyundur. CDN tek kaynaktan (CDN sabiti) gelir.

const CDN = 'https://unpkg.com/kaplay@3001.0.19/dist/kaplay.js';

function wrap(title, gameCode) {
  return `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<style>html,body{margin:0;height:100%;background:#0b0b12;overflow:hidden}canvas{display:block;margin:0 auto}</style>
</head>
<body>
<script src="${CDN}"></script>
<script>
window.kaboom = window.kaboom || window.kaplay;
${gameCode}
</script>
</body>
</html>`;
}

// ─── Kaçış / dodge ─────────────────────────────────────────────
const DODGE = wrap('Kaçış Oyunu', `kaplay({ width: 800, height: 600, background: [18, 18, 28], letterbox: true });

scene("oyun", () => {
  let skor = 0;
  const skorMetni = add([ text("Skor: 0", { size: 24 }), pos(12, 12) ]);
  add([ text("← → ok tuşlarıyla kaç", { size: 18 }), pos(12, height() - 32), color(180, 180, 180) ]);

  const oyuncu = add([
    rect(48, 48), pos(width() / 2, height() - 60), color(80, 200, 120),
    area(), anchor("center"), "oyuncu",
  ]);

  const HIZ = 400;
  onKeyDown("left", () => oyuncu.move(-HIZ, 0));
  onKeyDown("right", () => oyuncu.move(HIZ, 0));
  oyuncu.onUpdate(() => { oyuncu.pos.x = clamp(oyuncu.pos.x, 24, width() - 24); });

  loop(0.7, () => {
    add([
      rect(40, 40), pos(rand(20, width() - 20), -40), color(230, 80, 80),
      area(), anchor("center"), move(0, rand(180, 340)), offscreen({ destroy: true }), "dusman",
    ]);
  });

  loop(0.5, () => { skor += 1; skorMetni.text = "Skor: " + skor; });

  oyuncu.onCollide("dusman", () => go("bitti", skor));
});

scene("bitti", (skor) => {
  add([ text("Oyun Bitti!", { size: 48 }), pos(center().sub(0, 40)), anchor("center") ]);
  add([ text("Skor: " + skor, { size: 28 }), pos(center().add(0, 20)), anchor("center") ]);
  add([ text("Tekrar için BOŞLUK", { size: 20 }), pos(center().add(0, 70)), anchor("center"), color(180, 180, 180) ]);
  onKeyPress("space", () => go("oyun"));
});

go("oyun");`);

// ─── Yılan / snake ─────────────────────────────────────────────
const SNAKE = wrap('Yılan Oyunu', `kaplay({ width: 800, height: 600, background: [15, 22, 16], letterbox: true });

const GRID = 40, COLS = 20, ROWS = 15;

scene("oyun", () => {
  let yon = vec2(1, 0);
  let sonYon = vec2(1, 0);
  let yilan = [ vec2(5, 7), vec2(4, 7), vec2(3, 7) ];
  let yem = vec2(13, 7);
  let skor = 0;
  let bitti = false;

  const skorMetni = add([ text("Skor: 0", { size: 22 }), pos(10, 8) ]);
  add([ text("Ok tuşlarıyla yönlendir", { size: 16 }), pos(10, height() - 26), color(150, 200, 150) ]);

  onKeyPress("up", () => { if (sonYon.y === 0) yon = vec2(0, -1); });
  onKeyPress("down", () => { if (sonYon.y === 0) yon = vec2(0, 1); });
  onKeyPress("left", () => { if (sonYon.x === 0) yon = vec2(-1, 0); });
  onKeyPress("right", () => { if (sonYon.x === 0) yon = vec2(1, 0); });

  function ciz() {
    destroyAll("hucre");
    add([ rect(GRID - 2, GRID - 2), pos(yem.x * GRID + 1, yem.y * GRID + 1), color(230, 80, 80), "hucre" ]);
    yilan.forEach((s, i) => {
      add([ rect(GRID - 2, GRID - 2), pos(s.x * GRID + 1, s.y * GRID + 1), color(i === 0 ? 130 : 80, 220, 120), "hucre" ]);
    });
  }

  loop(0.12, () => {
    if (bitti) return;
    sonYon = yon;
    const bas = yilan[0].add(yon);
    if (bas.x < 0 || bas.y < 0 || bas.x >= COLS || bas.y >= ROWS || yilan.some((s) => s.x === bas.x && s.y === bas.y)) {
      bitti = true;
      go("bitti", skor);
      return;
    }
    yilan.unshift(bas);
    if (bas.x === yem.x && bas.y === yem.y) {
      skor += 1;
      skorMetni.text = "Skor: " + skor;
      yem = vec2(randi(0, COLS), randi(0, ROWS));
    } else {
      yilan.pop();
    }
    ciz();
  });

  ciz();
});

scene("bitti", (skor) => {
  add([ text("Oyun Bitti!", { size: 48 }), pos(center().sub(0, 40)), anchor("center") ]);
  add([ text("Skor: " + skor, { size: 28 }), pos(center().add(0, 20)), anchor("center") ]);
  add([ text("Tekrar için BOŞLUK", { size: 20 }), pos(center().add(0, 70)), anchor("center"), color(150, 200, 150) ]);
  onKeyPress("space", () => go("oyun"));
});

go("oyun");`);

// ─── Toplama / catch ───────────────────────────────────────────
const CATCH = wrap('Toplama Oyunu', `kaplay({ width: 800, height: 600, background: [22, 18, 32], letterbox: true });

scene("oyun", () => {
  let skor = 0;
  let can = 3;
  const skorMetni = add([ text("Skor: 0", { size: 22 }), pos(10, 8) ]);
  const canMetni = add([ text("Can: 3", { size: 22 }), pos(width() - 120, 8) ]);
  add([ text("← → ile sepeti hareket ettir", { size: 16 }), pos(10, height() - 26), color(200, 200, 160) ]);

  const sepet = add([
    rect(96, 28), pos(width() / 2, height() - 40), color(240, 200, 90),
    area(), anchor("center"), "sepet",
  ]);

  const HIZ = 440;
  onKeyDown("left", () => sepet.move(-HIZ, 0));
  onKeyDown("right", () => sepet.move(HIZ, 0));
  sepet.onUpdate(() => { sepet.pos.x = clamp(sepet.pos.x, 48, width() - 48); });

  loop(0.9, () => {
    add([
      circle(16), pos(rand(30, width() - 30), -20), color(120, 220, 250),
      area(), anchor("center"), move(0, rand(160, 280)), "elma",
    ]);
  });

  onUpdate("elma", (e) => {
    if (e.pos.y > height() + 20) {
      destroy(e);
      can -= 1;
      canMetni.text = "Can: " + can;
      if (can <= 0) go("bitti", skor);
    }
  });

  sepet.onCollide("elma", (e) => {
    destroy(e);
    skor += 1;
    skorMetni.text = "Skor: " + skor;
  });
});

scene("bitti", (skor) => {
  add([ text("Oyun Bitti!", { size: 48 }), pos(center().sub(0, 40)), anchor("center") ]);
  add([ text("Skor: " + skor, { size: 28 }), pos(center().add(0, 20)), anchor("center") ]);
  add([ text("Tekrar için BOŞLUK", { size: 20 }), pos(center().add(0, 70)), anchor("center"), color(200, 200, 160) ]);
  onKeyPress("space", () => go("oyun"));
});

go("oyun");`);

// ─── Flappy (yerçekimli — elle doğrulandı) ─────────────────────
const FLAPPY = wrap('Flappy', `kaplay({ width: 800, height: 600, background: [120, 200, 235], letterbox: true });
setGravity(1600);

scene("oyun", () => {
  let skor = 0;
  const skorMetni = add([ text("Skor: 0", { size: 28 }), pos(16, 16), color(30, 30, 30) ]);
  add([ text("BOŞLUK veya tıkla: zıpla", { size: 18 }), pos(16, height() - 30), color(40, 40, 40) ]);

  const kus = add([
    rect(40, 40), pos(170, height() / 2), color(250, 220, 70),
    area(), body(), anchor("center"), "kus",
  ]);

  onKeyPress("space", () => kus.jump(560));
  onClick(() => kus.jump(560));

  add([ rect(width(), 40), pos(0, height() - 40), area(), body({ isStatic: true }), color(90, 170, 80), "zemin" ]);

  const BOSLUK = 175;
  loop(1.5, () => {
    const delik = rand(110, height() - 150 - BOSLUK);
    add([ rect(72, delik), pos(width(), 0), area(), move(-220, 0), offscreen({ destroy: true }), color(70, 180, 90), "boru" ]);
    add([ rect(72, height() - delik - BOSLUK - 40), pos(width(), delik + BOSLUK), area(), move(-220, 0), offscreen({ destroy: true }), color(70, 180, 90), "boru" ]);
    add([ rect(4, BOSLUK), pos(width(), delik), area(), move(-220, 0), offscreen({ destroy: true }), opacity(0), "kapi" ]);
  });

  kus.onCollide("boru", () => go("bitti", skor));
  kus.onCollide("zemin", () => go("bitti", skor));
  kus.onCollide("kapi", (k) => { destroy(k); skor += 1; skorMetni.text = "Skor: " + skor; });
  kus.onUpdate(() => { if (kus.pos.y < 0) go("bitti", skor); });
});

scene("bitti", (skor) => {
  add([ text("Oyun Bitti!", { size: 48 }), pos(center().sub(0, 40)), anchor("center") ]);
  add([ text("Skor: " + skor, { size: 28 }), pos(center().add(0, 20)), anchor("center") ]);
  add([ text("Tekrar için BOŞLUK", { size: 20 }), pos(center().add(0, 70)), anchor("center"), color(40, 40, 40) ]);
  onKeyPress("space", () => go("oyun"));
});

go("oyun");`);

const TEMPLATES = { dodge: DODGE, snake: SNAKE, catch: CATCH, flappy: FLAPPY };

const GENRE_KEYWORDS = {
  flappy: ['flappy', 'kuş', 'kus', 'zıpla', 'zipla'],
  snake: ['yılan', 'yilan', 'snake'],
  catch: ['topla', 'yakala', 'catch', 'düşen', 'dusen', 'sepet'],
  dodge: ['kaç', 'kac', 'dodge', 'engel', 'kaçış', 'kacis'],
};

// İlk istekteki türü anahtar kelimeyle yakala. Spesifik türler (flappy/snake/
// catch) genel "kaç"tan önce denenir. Eşleşme yoksa null → serbest üretim.
export function detectGameGenre(text) {
  const t = (text || '').toLowerCase();
  for (const genre of ['flappy', 'snake', 'catch', 'dodge']) {
    if (GENRE_KEYWORDS[genre].some((k) => t.includes(k))) return genre;
  }
  return null;
}

export function getTemplate(genre) {
  return TEMPLATES[genre] || null;
}
