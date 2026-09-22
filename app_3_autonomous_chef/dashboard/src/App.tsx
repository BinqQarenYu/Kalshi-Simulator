import React from 'react';
import { BaseButton } from '@shared/ui';

function App() {
  return (
    <div className="min-h-screen p-8 font-mono">
      <h1 className="text-2xl font-bold text-emerald-500 mb-4">Supervisor Configuration</h1>
      <p className="text-slate-400 mb-6">Hyperparameter Tuning Controls & Log Streams.</p>
      <BaseButton>Initialize app_3_autonomous_chef</BaseButton>
    </div>
  );
}

export default App;
