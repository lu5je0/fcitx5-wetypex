#include "../src/common/json.hpp"
#include <iostream>
#include <string>

static int failures = 0;
static void expect(bool condition, const char *message) {
  if (!condition) {
    std::cerr << message << '\n';
    ++failures;
  }
}

int main() {
  // The actual backend sends raw UTF-8, rather than JSON \u escapes. An
  // ASCII-only ready message succeeds even with json-c 0.18's strict-mode
  // signed-char bug, while every Chinese candidate response is discarded.
  auto response = wire::parse(
      R"({"session":2,"seq":6,"epoch":1,"preedit":"nihao","display_preedit":"ni'hao","candidates":["你好","👋","你号"],"commits":[]})");
  expect(bool(response), "UTF-8 candidate response was rejected");
  expect(wire::str(response.get(), "display_preedit") == "ni'hao",
         "display preedit was lost");
  auto *candidates = wire::get(response.get(), "candidates");
  expect(candidates && json_object_array_length(candidates) == 3,
         "candidate list was lost");
  if (candidates && json_object_array_length(candidates) == 3) {
    expect(std::string(json_object_get_string(
               json_object_array_get_idx(candidates, 0))) == "你好",
           "Chinese candidate was changed");
    expect(std::string(json_object_get_string(
               json_object_array_get_idx(candidates, 1))) == "👋",
           "emoji candidate was changed");
  }

  auto settings = wire::object();
  wire::put(settings.get(), "phrase", std::string("你好👋"));
  auto roundTrip = wire::parse(wire::dump(settings.get()));
  expect(wire::str(roundTrip.get(), "phrase") == "你好👋",
         "UTF-8 settings failed a JSON round trip");
  auto committed = wire::parse(R"({"commits":["你好"]})");
  expect(bool(committed), "Chinese commit response was rejected");

  // The dependency fix must preserve strict parsing and UTF-8 rejection.
  for (const auto &invalid : {
           std::string("{\"text\":\"\xe4\xbd\"}"),
           std::string("{\"text\":\"\xff\"}"),
           std::string("{\"text\":\"line\nbreak\"}"),
           std::string("{\"value\":1} trailing"),
           std::string("{\"value\":1,}"),
       })
    expect(!wire::parse(invalid), "Malformed JSON/UTF-8 was accepted");
  expect(bool(wire::parse("{\"text\":\"ASCII\"}\n")),
         "ASCII JSON with trailing whitespace was rejected");
  return failures ? 1 : 0;
}
