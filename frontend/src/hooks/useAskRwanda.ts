import { useState, useCallback, useRef } from "react";
import { 
  AskRwandaMessageData, 
  AskRwandaSource, 
  RelatedContent,
  AskRwandaContext,
  AskRwandaFilter
} from "@/components/askrwanda";
import { toast } from "sonner";

interface UseAskRwandaOptions {
  context?: AskRwandaContext | null;
  filter?: AskRwandaFilter;
}

export function useAskRwanda(options: UseAskRwandaOptions = {}) {
  const [messages, setMessages] = useState<AskRwandaMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (userInput: string) => {
    if (!userInput.trim()) return;

    const userMessage: AskRwandaMessageData = {
      id: Date.now().toString(),
      role: "user",
      content: userInput.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    // Prepare context for the edge function
    const contextData = options.context ? {
      type: options.context.type,
      id: options.context.id,
      title: options.context.title,
    } : null;

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch(
        `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/ask-rwanda`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY}`,
          },
          body: JSON.stringify({
            messages: [...messages, userMessage].map(m => ({
              role: m.role,
              content: m.content,
            })),
            context: contextData,
            filter: options.filter || "all",
          }),
          signal: abortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("Rate limit exceeded. Please try again in a moment.");
        }
        if (response.status === 402) {
          throw new Error("AI credits exhausted. Please try again later.");
        }
        throw new Error("Failed to get response from Ask Rwanda");
      }

      // Handle streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantContent = "";
      let sources: AskRwandaSource[] = [];
      let relatedContent: RelatedContent[] = [];
      let isSensitive = false;

      const assistantMessageId = (Date.now() + 1).toString();

      // Create initial assistant message
      setMessages(prev => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          content: "",
          timestamp: new Date(),
        },
      ]);

      if (reader) {
        let textBuffer = "";
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          textBuffer += decoder.decode(value, { stream: true });

          // Process line-by-line as data arrives
          let newlineIndex: number;
          while ((newlineIndex = textBuffer.indexOf("\n")) !== -1) {
            let line = textBuffer.slice(0, newlineIndex);
            textBuffer = textBuffer.slice(newlineIndex + 1);

            if (line.endsWith("\r")) line = line.slice(0, -1);
            if (line.startsWith(":") || line.trim() === "") continue;
            if (!line.startsWith("data: ")) continue;

            const jsonStr = line.slice(6).trim();
            if (jsonStr === "[DONE]") break;

            try {
              const parsed = JSON.parse(jsonStr);
              
              // Handle metadata (sources, related content)
              if (parsed.metadata) {
                sources = parsed.metadata.sources || [];
                relatedContent = parsed.metadata.relatedContent || [];
                isSensitive = parsed.metadata.isSensitive || false;
                continue;
              }

              // Handle content delta
              const content = parsed.choices?.[0]?.delta?.content as string | undefined;
              if (content) {
                assistantContent += content;
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantMessageId
                      ? { ...m, content: assistantContent }
                      : m
                  )
                );
              }
            } catch {
              // Incomplete JSON, put it back and wait
              textBuffer = line + "\n" + textBuffer;
              break;
            }
          }
        }

        // Final update with sources and related content
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMessageId
              ? { ...m, sources, relatedContent, isSensitive }
              : m
          )
        );
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        return;
      }
      
      const errorMessage = err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      toast.error(errorMessage);
      
      // Remove the empty assistant message on error
      setMessages(prev => prev.filter(m => m.content !== ""));
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [messages, options.context, options.filter]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const cancelRequest = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    cancelRequest,
  };
}
