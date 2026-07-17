<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';

	type Item = {
		id: string;
		name?: string;
		description?: string;
		meta?: {
			description?: string;
		};
	};

	export let items: Item[] = [];
	export let placeholder = '';
	export let id = 'typeahead-selector';
	export let className = 'w-full';

	const dispatch = createEventDispatcher<{ select: Item }>();
	const listboxId = `${id}-options`;

	let value = '';
	let inputElement: HTMLInputElement | null = null;
	let popupElement: HTMLDivElement | null = null;
	let suggestionsOpen = false;

	$: query = value.trim().toLowerCase();
	$: filteredItems = (items ?? [])
		.filter((item) => {
			const itemId = item.id.toLowerCase();
			const name = (item.name ?? '').toLowerCase();
			const description = (item.description ?? item.meta?.description ?? '').toLowerCase();
			return (
				query === '' ||
				itemId.includes(query) ||
				name.includes(query) ||
				description.includes(query)
			);
		})
		.slice(0, 8);
	$: if (suggestionsOpen && filteredItems.length > 0) {
		tick().then(positionPopup);
	}

	const portal = (node: HTMLElement) => {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			}
		};
	};

	const positionPopup = () => {
		if (!inputElement || !popupElement) return;

		const rect = inputElement.getBoundingClientRect();
		const width = Math.min(192, rect.width, window.innerWidth - 16);
		popupElement.style.top = `${rect.bottom + 4}px`;
		popupElement.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`;
		popupElement.style.width = `${width}px`;
	};

	const selectItem = (item: Item) => {
		dispatch('select', item);
		value = '';
		suggestionsOpen = false;
	};

	const handlePointerDown = (event: PointerEvent) => {
		if (!suggestionsOpen) return;

		const target = event.target as Node;
		if (inputElement?.contains(target) || popupElement?.contains(target)) return;
		suggestionsOpen = false;
	};
</script>

<svelte:window
	on:pointerdown={handlePointerDown}
	on:scroll|capture={positionPopup}
	on:resize={positionPopup}
/>

<div class="mb-1 block">
	<input
		bind:this={inputElement}
		bind:value
		id={`${id}-input`}
		class="{className} text-sm bg-transparent outline-hidden"
		type="text"
		{placeholder}
		role="combobox"
		aria-autocomplete="list"
		aria-controls={listboxId}
		aria-expanded={suggestionsOpen && filteredItems.length > 0}
		autocomplete="off"
		on:focus={() => {
			suggestionsOpen = true;
			positionPopup();
		}}
		on:input={() => {
			suggestionsOpen = true;
			positionPopup();
		}}
		on:keydown={(event) => {
			if (event.key === 'Escape') suggestionsOpen = false;
		}}
		on:blur={() => {
			setTimeout(() => {
				if (!popupElement?.contains(document.activeElement)) suggestionsOpen = false;
			}, 0);
		}}
	/>
</div>

{#if suggestionsOpen && filteredItems.length > 0}
	<div
		use:portal
		bind:this={popupElement}
		id={listboxId}
		class="fixed max-h-48 overflow-y-auto rounded-2xl border border-gray-200 bg-white p-0.5 shadow-lg dark:border-gray-800 dark:bg-gray-850"
		role="listbox"
		style="z-index: 9999; top: 0; left: 0;"
	>
		{#each filteredItems as item (item.id)}
			<button
				type="button"
				class="flex w-full items-center justify-between gap-3 rounded-xl px-2 py-[5px] text-left text-xs text-gray-700 transition-colors hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-800"
				role="option"
				aria-selected={false}
				on:mousedown={(event) => event.preventDefault()}
				on:click={() => selectItem(item)}
			>
				<span class="truncate">{item.id}</span>
				{#if item.name && item.name !== item.id}
					<span class="truncate text-gray-500 dark:text-gray-400">{item.name}</span>
				{/if}
			</button>
		{/each}
	</div>
{/if}
