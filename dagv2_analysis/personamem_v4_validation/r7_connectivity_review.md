# R7 connectivity review

Release: `c10c6dab840a855de4233393ffba086a43e6772b`.

This bounded investigation was read-only. It issued two TCP connection probes and four non-generating `GET` requests to models-listing endpoints, without Authorization headers or retries. It changed no system networking, VPN, routes, source code, endpoint/model configuration, or credentials. The report contains no endpoint/proxy addresses, ports, keys, model names, or full configuration.

## Observations

All conventional uppercase and lowercase proxy environment variables are unset. However, Python discovers macOS system HTTP and HTTPS proxies whose addresses are loopback; neither service address bypasses them.

Both service addresses use the same **tunnel interface** route. They are configured as literal IP addresses, so hostname DNS resolution is not the blocking step. Direct TCP connection establishment succeeds in approximately 0.5 ms for both addresses.

| Service role | Per-request application proxy mode | Observed HTTP result | Time |
|---|---|---|---:|
| LLM | System default | HTTP 502 | 5.004 s |
| LLM | Disabled in this request opener only | `RemoteDisconnected` | 5.007 s |
| Embedding | System default | HTTP 502 | 5.004 s |
| Embedding | Disabled in this request opener only | `RemoteDisconnected` | 5.006 s |

No further HTTP requests were made after this comparison.

The ordinary generation transport uses `urllib.request.urlopen`, which discovers system proxies by default. The tokenization transport explicitly uses `ProxyHandler({})`. Crucially, application-level proxy bypass still follows the same system tunnel route; these probes did not compare two independent physical network paths.

## Supported conclusion

Both configured service interfaces currently have a **connection/HTTP-response-layer blocker** from this local environment. The active system proxy and common tunnel route are confirmed client-network factors. Bypassing the application proxy did not restore either service, so this evidence does not identify the loopback proxy alone as the root cause or establish that changing a setting would fix it.

Successful TCP establishment through a tunnel does not establish a working end-to-end HTTP service. The common five-second failures are consistent with a shared path or upstream failure, but cannot locate it uniquely: the local tunnel/upstream path and a shared remote gateway or service remain possible. No network configuration changes or additional independent-path tests were attempted.

These requests did not produce an authentication decision. They provide no basis for concluding that the keys are valid or invalid, that the configured model identity is wrong, or that model weights are unavailable. Record R7 as blocked by the two service connections, not as an algorithm failure or a completed validation run.

Structured safe results: `r7_connectivity_review.json`.
