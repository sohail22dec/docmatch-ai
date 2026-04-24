"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, User, Bot, Loader2, PlusCircle, MessageSquare, PanelLeftClose, PanelLeftOpen } from "lucide-react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Session = {
  id: string;
  title: string;
  created_at: string;
};

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Fetch all sessions on mount
  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/sessions");
      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions || []);
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  };

  const loadSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsLoading(true);
    setMessages([]); // Clear while loading
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}/messages`);
      if (response.ok) {
        const data = await response.json();
        // Backend returns DB objects, we map them to our Message type
        const formattedMessages = data.messages.map((msg: any) => ({
          role: msg.role,
          content: msg.content
        }));
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error("Failed to load session messages:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    const newMessages = [...messages, userMessage];
    
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          session_id: currentSessionId, 
          messages: newMessages // We send the list, backend extracts the latest
        }),
      });

      if (!response.ok) throw new Error("Failed to fetch response");

      const data = await response.json();
      
      setMessages([...newMessages, { role: "assistant", content: data.response }]);
      
      // If this was a new session, the backend created an ID for it.
      // We should update our currentSessionId and refresh the sidebar.
      if (!currentSessionId && data.session_id) {
        setCurrentSessionId(data.session_id);
        fetchSessions();
      }

    } catch (error) {
      console.error("Chat error:", error);
      setMessages([...newMessages, { 
        role: "assistant", 
        content: "Sorry, I encountered an error connecting to the server. Please ensure the backend is running." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] max-w-6xl mx-auto bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200">
      
      {/* Sidebar */}
      <div className={`${isSidebarOpen ? 'w-64' : 'w-0'} flex-shrink-0 bg-slate-50 border-r border-slate-200 transition-all duration-300 overflow-hidden flex flex-col`}>
        <div className="p-4 border-b border-slate-200">
          <button 
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 bg-white border border-slate-300 hover:border-blue-500 hover:text-blue-600 text-slate-700 py-2.5 rounded-lg transition-colors font-medium text-sm"
          >
            <PlusCircle size={18} />
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2">Recent Chats</p>
          {sessions.length === 0 ? (
            <p className="text-sm text-slate-400 px-2 italic">No past conversations</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => loadSession(session.id)}
                className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  currentSessionId === session.id 
                    ? 'bg-blue-100 text-blue-700 font-medium' 
                    : 'hover:bg-slate-200 text-slate-700'
                }`}
              >
                <MessageSquare size={16} className={currentSessionId === session.id ? "text-blue-600" : "text-slate-400"} />
                <span className="truncate">{session.title}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 p-4 text-white flex items-center shadow-sm z-10 shrink-0">
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="mr-4 p-1.5 hover:bg-white/20 rounded-md transition-colors"
            title={isSidebarOpen ? "Close Sidebar" : "Open Sidebar"}
          >
            {isSidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
          </button>
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Bot size={22} className="text-blue-100" />
              Medical Assistant
            </h2>
            {currentSessionId && (
              <p className="text-blue-200 text-xs mt-0.5 truncate">
                Session ID: {currentSessionId.split('-')[0]}...
              </p>
            )}
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 bg-white space-y-6">
          {messages.length === 0 && !isLoading ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
              <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-2 shadow-sm border border-slate-100">
                <Bot size={32} className="text-slate-400" />
              </div>
              <p className="text-lg font-medium text-slate-600">Start a new medical consultation</p>
              <p className="text-sm text-center max-w-sm">
                Describe your symptoms, and I can help search for medical information or provide general guidance.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div 
                key={idx} 
                className={`flex gap-3 sm:gap-4 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
              >
                <div className={`flex-shrink-0 w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shadow-sm ${
                  msg.role === "user" 
                    ? "bg-gradient-to-br from-indigo-500 to-blue-600 text-white" 
                    : "bg-white border-2 border-blue-100 text-blue-600"
                }`}>
                  {msg.role === "user" ? <User size={18} /> : <Bot size={20} />}
                </div>
                <div className={`max-w-[85%] sm:max-w-[80%] rounded-2xl p-4 shadow-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-tr-sm"
                    : "bg-slate-50 border border-slate-100 text-slate-800 rounded-tl-sm prose prose-sm sm:prose-base prose-blue max-w-none"
                }`}>
                  {msg.content.split('\n').map((line, i) => (
                    <span key={i}>
                      {line}
                      <br />
                    </span>
                  ))}
                </div>
              </div>
            ))
          )}
          
          {isLoading && (
            <div className="flex gap-4">
              <div className="w-10 h-10 rounded-full bg-white border-2 border-blue-100 flex items-center justify-center text-blue-600 shadow-sm">
                <Bot size={20} />
              </div>
              <div className="bg-slate-50 border border-slate-100 rounded-2xl rounded-tl-sm p-4 text-slate-500 flex items-center gap-3 shadow-sm">
                <Loader2 size={18} className="animate-spin text-blue-500" />
                <span className="text-sm">Analyzing and thinking...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-100 shrink-0">
          <form onSubmit={handleSubmit} className="relative flex items-center max-w-4xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your symptoms or questions here..."
              className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-sm sm:text-base rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 block p-3 sm:p-4 pr-12 sm:pr-14 outline-none transition-all shadow-inner"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="absolute right-2 p-2 sm:p-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
            >
              <Send size={18} className="sm:w-5 sm:h-5" />
            </button>
          </form>
          <p className="text-center text-xs text-slate-400 mt-3">
            This is an AI assistant, not a doctor. In case of emergency, call 911.
          </p>
        </div>
      </div>
    </div>
  );
}
