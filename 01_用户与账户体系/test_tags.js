const fs = require('fs');
const html = fs.readFileSync('C端_用户签约与保密协议演示.html', 'utf8');
const lines = html.split('\n');
let divCount = 0;
for(let i = 133; i < 213; i++) {
  const line = lines[i];
  const opens = (line.match(/<div/g) || []).length;
  const closes = (line.match(/<\/div>/g) || []).length;
  divCount += (opens - closes);
  if (i === 134 || i === 210 || i === 211 || i === 212) {
      console.log(`Line ${i+1}: ${line.trim()} (depth diff: ${opens - closes}, total: ${divCount})`);
  }
}
