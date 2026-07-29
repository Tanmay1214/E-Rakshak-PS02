const fs = require('fs');

const traverse = (dir) => {
  fs.readdirSync(dir).forEach(file => {
    let fullPath = dir + '/' + file;
    if (fs.statSync(fullPath).isDirectory()) {
      traverse(fullPath);
    } else if (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      
      // Fix types imports
      content = content.replace(/import\s+{([^}]+)}\s+from\s+(['"])\.\.\/types\/evidence\2/g, 'import type { $1 } from $2../types/evidence$2');
      
      // Fix unused React imports
      content = content.replace(/import\s+React\s+from\s+['"]react['"];?\s*/g, '');
      content = content.replace(/import\s+React,\s+{/g, 'import {');
      
      if (content.includes('React.ReactNode')) {
        content = content.replace(/React\.ReactNode/g, 'ReactNode');
        if (content.includes('import {')) {
            content = content.replace('import {', 'import { ReactNode,');
        } else {
            content = "import { ReactNode } from 'react';\n" + content;
        }
      }
      fs.writeFileSync(fullPath, content);
    }
  });
};

traverse('c:/rakshak/E-Rakshak-PS02/dashboard/src');
