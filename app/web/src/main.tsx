import { render } from "@solidjs/web";
import { App } from "./App";
import { initAnalytics } from "./analytics";
import "./index.css";

initAnalytics();
render(() => <App />, document.getElementById("root")!);
