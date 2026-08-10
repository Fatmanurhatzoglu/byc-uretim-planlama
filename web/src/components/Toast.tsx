"use client";

import { useEffect, useState } from "react";

export function Toast({ message }: { message: string }) {
  const [visible, setVisible] = useState(!!message);

  useEffect(() => {
    if (!message) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), 3200);
    return () => clearTimeout(t);
  }, [message]);

  if (!visible || !message) return null;
  return <div className="mob-toast">{message}</div>;
}

export function useToast() {
  const [msg, setMsg] = useState("");
  const show = (text: string) => setMsg(text);
  return { message: msg, show };
}
