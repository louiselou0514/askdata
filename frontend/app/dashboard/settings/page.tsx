"use client";

import { useEffect, useState } from "react";

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-xl font-semibold text-gray-900 mb-1">Settings</h1>
      <p className="text-sm text-gray-400 mb-6">
        Configure your AskData workspace.
      </p>
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <p className="text-sm text-gray-500">
          Business glossary and user management coming in Phase 2.
        </p>
      </div>
    </div>
  );
}
