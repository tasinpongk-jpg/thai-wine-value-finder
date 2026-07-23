import { Container, getContainer } from "@cloudflare/containers";

type Env = {
	WINE_VALUE_CONTAINER: DurableObjectNamespace<WineValueContainer>;
};

export class WineValueContainer extends Container<Env> {
	defaultPort = 8501;
	sleepAfter = "10m";
	envVars = {
		WINEVALUE_PUBLIC_MODE: "1",
		WINEVALUE_CELLAR_DB: "/tmp/wine-value-public-cellar.db",
	};

	override onStart() {
		console.log("Wine Value Finder container started");
	}

	override onStop() {
		console.log("Wine Value Finder container stopped");
	}

	override onError(error: unknown) {
		console.error("Wine Value Finder container error", error);
	}
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const container = getContainer(env.WINE_VALUE_CONTAINER, "production");
		return container.fetch(request);
	},
} satisfies ExportedHandler<Env>;
