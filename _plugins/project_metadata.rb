# Jekyll's Liquid document drop reserves `collection` for the collection type.
# Read the author's front matter directly and expose a separate rendering value.
Jekyll::Hooks.register :site, :post_read do |site|
  projects = site.collections["projects"]
  next unless projects

  projects.docs.each do |project|
    project.data["collection_label"] = project.data.fetch(
      "collection", project.data["collection_name"]
    ).to_s.strip
  end
end
