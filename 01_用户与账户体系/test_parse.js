const fs = require('fs');
const html = fs.readFileSync('C端_用户签约与保密协议演示.html', 'utf8');
const lines = html.split('\n');
console.log("Lines containing '情况B':");
lines.forEach((line, i) => {
  if (line.includes('情况B')) console.log(`${i+1}: ${line.trim()}`);
});
