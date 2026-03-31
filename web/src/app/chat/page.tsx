import { NavHeader } from "@/components/layout/nav-header";
import { ChatPanel } from "@/components/chat/chat-panel";

export default function ChatPage() {
  return (
    <div className="flex flex-1 flex-col">
      <NavHeader />
      <ChatPanel />
    </div>
  );
}
