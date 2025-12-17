const express = require('express');
const cors = require('cors');
const app = express();

// Разрешим запросы с вашего фронтенда
app.use(cors({
  origin: ['http://localhost:3000']  // порт вашего React dev-сервера
}));

// Данные отчёта
const reportHeader = 'Прайс Лист BionicPRO';
const columns = ['протез', 'цена'];
const rows = [
  ['нога', '1 млн'],
  ['рука', '2 млн'],
  ['голова', '5 млн'],
  ['глаз', '6 млн'],
  ['ягодицы', '0,5 млн'],
  ['почка', '10 млн'],
  ['жабры', '100 млн'],
  ['инфракрасное зрение', '100 млн'],
];

// Утилита: собрать CSV-строку
function generateCsv() {
  let out = reportHeader + '\r\n';
  out += columns.join(',') + '\r\n';
  for (const r of rows) {
    out += r.join(',') + '\r\n';
  }
  return out;
}

// Эндпоинт /reports
app.get('/reports', (req, res) => {
  const filename = 'price_list_bionicpro.csv';
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="${filename}"');
  res.send(generateCsv());
});

// Стартуем на 8000 порту
const PORT = 8000;
app.listen(PORT, () => {
  console.log('BionicPRO-backend listening on http://localhost:${PORT}');
});
