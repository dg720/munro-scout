import { useState } from "react";
import { Box, Heading, Text, Input, Flex, Button } from "@chakra-ui/react";

export type ChatMessage = { role: "user" | "assistant"; content: string };

type Props = {
  messages: ChatMessage[];
  onSend: (text: string) => void;
};

export default function ChatTab({ messages, onSend }: Props) {
  const [input, setInput] = useState("");

  const submit = () => {
    const text = input.trim();
    if (!text) return;
    onSend(text);
    setInput("");
  };

  return (
    <Box mt={6}>
      <Heading size="md" mb={4}>Munro Scout Assistant</Heading>

      <Box
        bg="gray.50"
        p={4}
        rounded="lg"
        maxH="400px"
        overflowY="auto"
        mb={4}
        border="1px solid #e2e8f0"
      >
        {messages.map((msg, idx) => (
          <Box key={idx} mb={3} textAlign={msg.role === "user" ? "right" : "left"}>
            <Text
              display="inline-block"
              bg={msg.role === "user" ? "blue.100" : "gray.200"}
              px={3}
              py={2}
              rounded="xl"
              maxW="80%"
            >
              {msg.content}
            </Text>
          </Box>
        ))}
      </Box>

      <Flex gap={2}>
        <Input
          placeholder="Ask about Munros..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
        />
        <Button onClick={submit} colorScheme="blue">
          Send
        </Button>
      </Flex>
    </Box>
  );
}
