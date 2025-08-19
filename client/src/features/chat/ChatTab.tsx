import { useState } from "react";
import {
  Box, Heading, Text, Input, Flex, Button, Spinner,
  Accordion, AccordionItem, AccordionButton, AccordionPanel, AccordionIcon,
  Stack, Tag, Code, Badge, useToast
} from "@chakra-ui/react";

type ChatMessage = { role: "user" | "assistant"; content: string; steps?: any };

const API_BASE =
  (typeof process !== "undefined" && (process as any)?.env?.REACT_APP_API_BASE) ||
  "http://localhost:5000";


export default function ChatTab() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const submit = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, limit: 8 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const answer = (data?.answer ?? "").trim() || "(no answer)";
      const steps = data?.steps ?? null;
      setMessages((m) => [...m, { role: "assistant", content: answer, steps }]);
    } catch (err: any) {
      toast({
        title: "Chat error",
        description: err?.message || "Something went wrong calling /api/chat",
        status: "error",
        duration: 4000,
        isClosable: true,
      });
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Sorry — I couldn’t reach the server." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box mt={6}>
      <Heading size="md" mb={4}>Munro Scout Assistant</Heading>

      <Box
        bg="gray.50"
        p={4}
        rounded="lg"
        maxH="480px"
        overflowY="auto"
        mb={4}
        border="1px solid #e2e8f0"
      >
        {messages.map((msg, idx) => (
          <Box key={idx} mb={4} textAlign={msg.role === "user" ? "right" : "left"}>
            <Text
              display="inline-block"
              bg={msg.role === "user" ? "blue.100" : "gray.200"}
              px={3}
              py={2}
              rounded="xl"
              maxW="80%"
              whiteSpace="pre-wrap"
            >
              {msg.content}
            </Text>

            {msg.role === "assistant" && msg.steps && (
              <Box mt={2} maxW="80%" ml={0}>
                <Inspector steps={msg.steps} />
              </Box>
            )}
          </Box>
        ))}

        {loading && (
          <Flex align="center" gap={2}>
            <Spinner size="sm" />
            <Text fontSize="sm" color="gray.600">Thinking…</Text>
          </Flex>
        )}
      </Box>

      <Flex gap={2}>
        <Input
          placeholder="Ask about Munros… e.g. 'airy scramble by bus near Glen Coe'"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
          isDisabled={loading}
        />
        <Button onClick={submit} colorScheme="blue" isLoading={loading}>
          Send
        </Button>
      </Flex>
    </Box>
  );
}

function Inspector({ steps }: { steps: any }) {
  const intent = steps?.intent ?? {};
  const sql = steps?.retrieval_sql ?? "";
  const params = steps?.retrieval_params ?? [];
  const results = (steps?.candidates ?? []) as Array<{
    id: number;
    name: string;
    tags: string[];
    snippet: string;
    rank: number;
  }>;

  return (
    <Accordion allowToggle>
      <AccordionItem border="none">
        <AccordionButton
          _expanded={{ bg: "gray.100" }}
          px={2}
          py={1}
          borderRadius="md"
          fontSize="sm"
        >
          <Box as="span" flex="1" textAlign="left">
            How I searched (intent, SQL & results)
          </Box>
          <AccordionIcon />
        </AccordionButton>
        <AccordionPanel pb={4}>
          <Box mb={3}>
            <Text fontWeight="semibold" mb={1} fontSize="sm">Intent</Text>
            <Code p={2} w="100%" whiteSpace="pre-wrap" fontSize="xs">
              {JSON.stringify(intent, null, 2)}
            </Code>
          </Box>

          <Box mb={3}>
            <Text fontWeight="semibold" mb={1} fontSize="sm">SQL</Text>
            <Code p={2} w="100%" whiteSpace="pre-wrap" fontSize="xs">
              {sql}
            </Code>
            <Text mt={1} fontSize="xs" color="gray.600">Params: {JSON.stringify(params)}</Text>
          </Box>

          <Box>
            <Text fontWeight="semibold" mb={2} fontSize="sm">Top results</Text>
            <Stack spacing={3}>
              {results.map((r) => (
                <Box key={r.id} p={3} bg="white" border="1px solid #e2e8f0" rounded="md">
                  <Flex justify="space-between" align="center" mb={1}>
                    <Text fontWeight="bold">{r.name}</Text>
                    <Badge variant="subtle">BM25 {r.rank.toFixed(2)}</Badge>
                  </Flex>
                  <Flex gap={1} wrap="wrap" mb={2}>
                    {r.tags.slice(0, 14).map((t) => (
                      <Tag key={t} size="sm">{t}</Tag>
                    ))}
                  </Flex>
                  <Text fontSize="sm" color="gray.700">
                    {r.snippet}
                    {r.snippet?.length >= 400 ? "…" : ""}
                  </Text>
                </Box>
              ))}
              {results.length === 0 && (
                <Text fontSize="sm" color="gray.600">No results from the current filters.</Text>
              )}
            </Stack>
          </Box>
        </AccordionPanel>
      </AccordionItem>
    </Accordion>
  );
}
