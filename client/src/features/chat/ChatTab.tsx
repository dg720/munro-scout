import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Heading,
  Text,
  Input,
  Flex,
  Button,
  Spinner,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Stack,
  Tag,
  Code,
  useToast,
  HStack,
  Divider,
  Icon,
} from "@chakra-ui/react";
import { InfoOutlineIcon, QuestionOutlineIcon, RepeatIcon } from "@chakra-ui/icons";

export type ChatRouteLink = { id: number; name: string; tags?: string[] };
export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  steps?: any;
  routes?: ChatRouteLink[];
};

type Props = {
  messages: ChatMessage[];
  onSend: (text: string) => Promise<void> | void;
  onOpenRoute: (route: ChatRouteLink) => void;
  onReset: () => void; // NEW: parent clears the conversation
};

const API_BASE =
  (typeof process !== "undefined" && (process as any)?.env?.REACT_APP_API_BASE) ||
  "http://localhost:5000";

export default function ChatTab({ messages, onSend, onOpenRoute, onReset }: Props) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Autoscroll when messages/loading change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const examplePrompts = useMemo(
    () => [
      "find quiet hikes near Edinburgh accessible by train",
      "identify ridgewalks with great views near Torridon",
      "search for hikes with exposed scrambling on the Isle of Skye",
      "suggest hikes under 6 hours and <15km near Aviemore",
    ],
    []
  );

  const submit = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);

    try {
      onSend(text); // optimistic append by parent

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, limit: 8 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const answer = (data?.answer ?? "").trim() || "(no answer)";
      const steps = data?.steps ?? null;
      const routes = (data?.routes ?? []) as ChatRouteLink[];

      // Emit assistant message so parent can persist/render
      window.dispatchEvent(
        new CustomEvent("munro-chat-assistant", {
          detail: { content: answer, steps, routes },
        })
      );
    } catch (err: any) {
      toast({
        title: "Chat error",
        description: err?.message || "Something went wrong calling /api/chat",
        status: "error",
        duration: 4000,
        isClosable: true,
      });
      window.dispatchEvent(
        new CustomEvent("munro-chat-assistant", {
          detail: { content: "Sorry — I couldn’t reach the server." },
        })
      );
    } finally {
      setLoading(false);
    }
  };

  // Append helper for tags
  const appendTag = (t: string) =>
    setInput((prev) => (prev.trim() ? `${prev.trim()} ${t}` : t));

  // Reset handler (clear input locally, ask parent to clear messages)
  const handleReset = () => {
    setInput("");
    onReset();
  };

  return (
    <Box mt={6}>
      <Flex align="center" justify="space-between" mb={2}>
        <Heading size="md">Chat Assistant</Heading>

        {/* Reset button only shows if chat has messages */}
        {messages.length > 0 && (
          <Button size="sm" variant="ghost" colorScheme="red" onClick={handleReset}>
            Reset Chat
          </Button>
        )}
      </Flex>

      {/* Quick, visible description (outside the collapsible) */}
      <Box mb={3} p={3} bg="gray.50" border="1px solid #e2e8f0" rounded="md">
        <Text fontSize="sm">
          Munro Scout is an interactive hiking assistant designed to make exploring Scotland’s
          Munros easier and more intuitive. Users can ask for routes and mountain details in
          natural language, generating suggestions augmented by Walkhighlands data. The platform
          combines route data, GPX files, and searchable tags to identify hikes by difficulty,
          terrain, duration, or accessibility.
        </Text>
      </Box>

      {/* Chat window */}
      <Box
        ref={scrollRef}
        bg="gray.50"
        p={4}
        rounded="lg"
        maxH="480px"
        overflowY="auto"
        mb={4}
        border="1px solid #e2e8f0"
      >
        {messages.length === 0 ? (
          <EmptyState
            examples={examplePrompts}
            onExampleClick={setInput} // examples replace input by design
            onTagClick={appendTag} // tags append to input
          />
        ) : (
          <>
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

                {/* Route buttons (from backend/fallback) */}
                {msg.role === "assistant" && (msg.routes?.length ?? 0) > 0 && (
                  <HStack mt={2} spacing={2} flexWrap="wrap">
                    {msg.routes!.map((r) => (
                      <Button
                        key={r.id}
                        size="xs"
                        variant="outline"
                        onClick={() => onOpenRoute(r)}
                      >
                        Open “{r.name}”
                      </Button>
                    ))}
                  </HStack>
                )}

                {/* Inspector (debug) */}
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
                <Text fontSize="sm" color="gray.600">
                  Thinking…
                </Text>
              </Flex>
            )}
          </>
        )}
      </Box>

      {/* Input bar */}
      <Flex gap={2} position="sticky" bottom={0} bg="white" pb={1}>
        <Input
          aria-label="Chat input"
          placeholder="Ask about Munros… e.g. 'airy scramble by bus'"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          isDisabled={loading}
        />
        <Button
          onClick={submit}
          colorScheme="blue"
          isLoading={loading}
          rightIcon={<Icon as={RepeatIcon} />}
        >
          Send
        </Button>
      </Flex>

      {/* Collapsible footer — closed by default */}
      <Box mt={4}>
        <Accordion allowToggle defaultIndex={[]}>
          <AccordionItem border="1px solid #e2e8f0" borderRadius="md">
            <h2>
              <AccordionButton _expanded={{ bg: "gray.50" }} px={4} py={3}>
                <HStack flex="1" textAlign="left" spacing={3}>
                  <Icon as={InfoOutlineIcon} />
                  <Text fontWeight="semibold">About this tab</Text>
                </HStack>
                <AccordionIcon />
              </AccordionButton>
            </h2>
            <AccordionPanel pb={4} px={4}>
              <Stack spacing={4} fontSize="sm" color="gray.800">
                <Box>
                  <Heading size="sm" mb={1}>
                    How the search works
                  </Heading>
                  <Stack spacing={2} pl={1}>
                    <Text>
                      1. <b>Understand the request</b> — Parse the message for place names, terrain
                      words (e.g., “ridge”, “scramble”), and limits like time or distance.
                    </Text>
                    <Text>
                      2. <b>Search</b> — Use a fast text index for words, and standard SQL filters
                      for numbers such as time, distance, grade, and bog.
                    </Text>
                    <Text>
                      3. <b>Summarise</b> — Build a short answer based on the top matches and
                      include buttons to open route details.
                    </Text>
                  </Stack>
                </Box>

                <Divider />

                <Box>
                  <Heading size="sm" mb={1}>
                    What the backend does
                  </Heading>
                  <Stack spacing={2} pl={1}>
                    <Text>
                      • The LLM produces an intent JSON with keys like <Code>query</Code>,{" "}
                      <Code>include_tags</Code>, <Code>exclude_tags</Code>, <Code>bog_max</Code>,{" "}
                      <Code>grade_max</Code>, <Code>location</Code>, and numeric bounds (
                      <Code>distance_min_km</Code>, <Code>distance_max_km</Code>,{" "}
                      <Code>time_min_h</Code>, <Code>time_max_h</Code>).
                    </Text>
                    <Text>
                      • A location heuristic (regex) extracts places such as “near Fort William” if
                      the model misses them.
                    </Text>
                    <Text>
                      • A numeric parser catches phrases like “under 6 hours” →{" "}
                      <Code>time_max_h = 6</Code> or “between 10 and 15km”.
                    </Text>
                    <Text>
                      • If a location is present, <Code>search_by_location_core</Code> is used
                      (distance‑ranked, tags as soft boosts). Otherwise, <Code>search_core</Code>{" "}
                      runs FTS+SQL over text/tags with numeric limits.
                    </Text>
                    <Text>
                      • The response includes a <Code>steps</Code> block with intent, retrieval
                      mode, SQL, params, and results. The Inspector can display these for
                      transparency.
                    </Text>
                  </Stack>
                </Box>

                <Divider />

                <Box>
                  <Heading size="sm" mb={1}>
                    LLM‑assisted tagging
                  </Heading>
                  <Stack spacing={2} pl={1}>
                    <Text>
                      • The model reads a route description and selects tags from an approved list
                      (ontology), e.g., <Code>ridge</Code>, <Code>airy</Code>, <Code>handson</Code>
                      , <Code>river_crossing</Code>.
                    </Text>
                    <Text>
                      • Tags capture feel and terrain that numbers don’t, enabling queries like
                      “airy scramble with low bog”.
                    </Text>
                    <Text>
                      • Tags are normalised (lowercase, underscores), validated against the
                      ontology, and stored in <Code>tags</Code> / <Code>munro_tags</Code>. Batch
                      scripts can wipe and regenerate to avoid stale tags.
                    </Text>
                  </Stack>
                </Box>

                <Divider />

                <Box>
                  <HStack color="gray.600" mt={1}>
                    <Icon as={QuestionOutlineIcon} />
                    <Text>
                      Tip: expand the Inspector under any assistant message to view the parsed
                      intent, SQL, and results.
                    </Text>
                  </HStack>
                </Box>
              </Stack>
            </AccordionPanel>
          </AccordionItem>
        </Accordion>
      </Box>
    </Box>
  );
}

function EmptyState({
  examples,
  onExampleClick,
  onTagClick,
}: {
  examples: string[];
  onExampleClick: (p: string) => void;
  onTagClick: (t: string) => void;
}) {
  return (
    <Box textAlign="center" color="gray.700">
      <Heading size="sm" mb={2}>
        Start a conversation
      </Heading>
      <Text mb={4}>
        Ask for Munros by terrain, difficulty, access, distance/time, or tags.
      </Text>

      {/* Put examples on separate rows to avoid horizontal overlap */}
      <Stack spacing={2} align="stretch" maxW="600px" mx="auto" mb={4}>
        {examples.map((p) => (
          <Button key={p} size="sm" variant="outline" onClick={() => onExampleClick(p)}>
            {p}
          </Button>
        ))}
      </Stack>

      <Divider my={4} />

      <Stack spacing={2} align="center">
        <Text fontWeight="semibold">Example tags</Text>
        <HStack spacing={1} wrap="wrap" justify="center">
          {[
            "ridge",
            "scramble",
            "airy",
            "rocky",
            "knifeedge",
            "easy",
            "hard",
            "pathless",
            "river_crossing",
            "views",
            "classic",
            "camping",
            "steep",
            "bus",
            "train"
          ].map((t) => (
            <Tag
              key={t}
              size="sm"
              colorScheme="gray"
              cursor="pointer"
              onClick={() => onTagClick(t)}
            >
              {t}
            </Tag>
          ))}
        </HStack>
      </Stack>
    </Box>
  );
}

function Inspector({ steps }: { steps: any }) {
  const intent = steps?.intent ?? {};
  const sql = steps?.sql ?? steps?.retrieval_sql ?? "";
  const params = steps?.params ?? steps?.retrieval_params ?? [];
  const results = (steps?.results ?? steps?.candidates ?? []) as Array<{
    id: number;
    name: string;
    tags: string[];
    summary?: string;
  }>;

  return (
    <Accordion allowToggle>
      <AccordionItem border="none">
        <AccordionButton _expanded={{ bg: "gray.100" }} px={2} py={1} borderRadius="md" fontSize="sm">
          <Box as="span" flex="1" textAlign="left">
            How I searched (intent, SQL & results)
          </Box>
          <AccordionIcon />
        </AccordionButton>
        <AccordionPanel pb={4}>
          <Box mb={3}>
            <Text fontWeight="semibold" mb={1} fontSize="sm">
              Intent
            </Text>
            <Code p={2} w="100%" whiteSpace="pre-wrap" fontSize="xs">
              {JSON.stringify(intent, null, 2)}
            </Code>
          </Box>

          <Box mb={3}>
            <Text fontWeight="semibold" mb={1} fontSize="sm">
              SQL
            </Text>
            <Code p={2} w="100%" whiteSpace="pre-wrap" fontSize="xs">
              {sql}
            </Code>
            <Text mt={1} fontSize="xs" color="gray.600">
              Params: {JSON.stringify(params)}
            </Text>
          </Box>

          <Box>
            <Text fontWeight="semibold" mb={2} fontSize="sm">
              Top results
            </Text>
            <Stack spacing={3}>
              {results.map((r) => (
                <Box key={r.id} p={3} bg="white" border="1px solid #e2e8f0" rounded="md">
                  <Text fontWeight="bold" mb={1}>
                    {r.name}
                  </Text>
                    <Flex gap={1} wrap="wrap" mb={2}>
                      {r.tags?.slice(0, 14).map((t) => (
                        <Tag key={t} size="sm">
                          {t}
                        </Tag>
                      ))}
                    </Flex>
                  <Text fontSize="sm" color="gray.700">
                    {r.summary || "No summary available."}
                  </Text>
                </Box>
              ))}
              {results.length === 0 && (
                <Text fontSize="sm" color="gray.600">
                  No results from the current filters.
                </Text>
              )}
            </Stack>
          </Box>
        </AccordionPanel>
      </AccordionItem>
    </Accordion>
  );
}
