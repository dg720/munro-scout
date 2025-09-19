import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider } from '@chakra-ui/react';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root')!);

root.render(
  <React.StrictMode>
    {/* ChakraProvider wires up global design tokens/theme */}
    <ChakraProvider>
      {/* Single-page application shell */}
      <App />
    </ChakraProvider>
  </React.StrictMode>
);

